"""Outgoing webhooks — HMAC-signed event POSTs to subscriber URLs (e.g. ERP360).

Lifecycle:
  emit_event(db, org_id, event_type, payload)
    → for each matching subscription, persist a WebhookDelivery row
       (status=QUEUED) with a deterministic HMAC-SHA256 signature
    → fires _attempt() synchronously; on failure leaves the row FAILED
       with next_attempt_at set for the outbox worker tick to retry

Retry policy: 3 attempts total with backoff [30s, 5min, 30min]. After the
third failure the row moves to DEAD_LETTER.

Receivers verify by reproducing HMAC-SHA256(secret, raw_body) and comparing
to the `X-IFPI-Signature` header. The `X-IFPI-Event-Id` header carries a
UUID for receiver-side idempotency dedupe.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from sqlalchemy.orm import Session

from models import WebhookDelivery, WebhookSubscription

logger = logging.getLogger("ifpi.webhooks")

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = [30, 300, 1800]
REQUEST_TIMEOUT = 8

# Sentinel URL scheme: any subscription pointing at `dry-run://…` will
# be signed + persisted normally but the HTTP POST is skipped. Delivery
# rows are stamped `status='DELIVERED', status_code=204, error='dry-run'`
# so the admin UI + audit trail show a full sign-off without touching
# an external endpoint. Useful for:
#   • Bootstrapping the ERP360 → IFPI direction before ERP360 exposes
#     their inbound URL (flip `target_url` to real value → live)
#   • Staging environments that must not spam prod webhook targets
DRY_RUN_URL_PREFIX = "dry-run://"


def sign(secret: str, raw_body: bytes) -> str:
    """HMAC-SHA256 hex digest. Used to sign outgoing requests and to verify
    incoming ones on the ERP360 side."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _matches(sub: WebhookSubscription, event_type: str) -> bool:
    try:
        events = json.loads(sub.events or "[]")
    except json.JSONDecodeError:
        return False
    return "*" in events or event_type in events


def _serialise(payload: dict) -> bytes:
    return json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")


def _attempt(db: Session, delivery: WebhookDelivery, sub: WebhookSubscription) -> None:
    """Fire one HTTP request. Mutates the delivery row + subscription row.
    Caller is responsible for db.commit()."""
    delivery.attempt_count = (delivery.attempt_count or 0) + 1
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "IFPI-Learning-Webhooks/1.0",
        "X-IFPI-Event-Id": delivery.event_id,
        "X-IFPI-Event-Type": delivery.event_type,
        "X-IFPI-Signature": delivery.signature,
        "X-IFPI-Signature-Algorithm": "HMAC-SHA256",
    }
    now = datetime.now(timezone.utc)

    # Dry-run short-circuit — persists as delivered without POST.
    if (sub.target_url or "").startswith(DRY_RUN_URL_PREFIX):
        delivery.status = "DELIVERED"
        delivery.status_code = 204
        delivery.error = "dry-run: no HTTP request sent"
        delivery.delivered_at = now
        delivery.next_attempt_at = None
        sub.last_success_at = now
        logger.info(
            "webhooks.dry_run: event=%s event_id=%s sub_id=%s "
            "target=%s sig=%s bytes=%d",
            delivery.event_type, delivery.event_id, sub.id,
            sub.target_url, delivery.signature[:12] + "…",
            len(delivery.payload or ""),
        )
        return

    try:
        resp = requests.post(sub.target_url, data=delivery.payload, headers=headers,
                             timeout=REQUEST_TIMEOUT)
        delivery.status_code = resp.status_code
        if 200 <= resp.status_code < 300:
            delivery.status = "DELIVERED"
            delivery.error = None
            delivery.delivered_at = now
            delivery.next_attempt_at = None
            sub.last_success_at = now
            return
        else:
            delivery.error = (resp.text or "")[:500]
    except Exception as e:  # noqa: BLE001
        delivery.error = f"{type(e).__name__}: {e}"[:500]
        delivery.status_code = None

    # Failure path
    sub.last_failure_at = now
    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = "DEAD_LETTER"
        delivery.next_attempt_at = None
    else:
        delivery.status = "FAILED"
        idx = min(delivery.attempt_count - 1, len(BACKOFF_SECONDS) - 1)
        delivery.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[idx])


def emit_event(db: Session, organization_id: int, event_type: str, payload: dict) -> int:
    """Persist + fire one delivery per matching subscription. Returns count fired.

    `payload` is wrapped in an envelope `{event_type, event_id, organization_id,
    occurred_at, data: <payload>}` so the receiver always has consistent shape.
    """
    subs = db.query(WebhookSubscription).filter(
        WebhookSubscription.organization_id == organization_id,
        WebhookSubscription.is_active.is_(True),
    ).all()
    if not subs:
        return 0

    fired = 0
    for sub in subs:
        if not _matches(sub, event_type):
            continue
        envelope = {
            "event_type": event_type,
            "event_id": uuid.uuid4().hex,
            "organization_id": organization_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }
        raw = _serialise(envelope)
        sig = sign(sub.secret, raw)
        delivery = WebhookDelivery(
            subscription_id=sub.id, organization_id=organization_id,
            event_type=event_type, event_id=envelope["event_id"],
            payload=raw.decode("utf-8"), signature=sig, status="QUEUED",
        )
        db.add(delivery)
        db.flush()
        _attempt(db, delivery, sub)
        fired += 1
    db.commit()
    return fired


def drain_failed(db: Session, *, limit: int = 50) -> int:
    """Retry rows in FAILED status whose next_attempt_at is due. Returns count retried."""
    now = datetime.now(timezone.utc)
    rows = db.query(WebhookDelivery).filter(
        WebhookDelivery.status == "FAILED",
        WebhookDelivery.next_attempt_at.isnot(None),
        WebhookDelivery.next_attempt_at <= now,
    ).limit(limit).all()
    if not rows:
        return 0
    n = 0
    for d in rows:
        sub = db.query(WebhookSubscription).filter(WebhookSubscription.id == d.subscription_id).first()
        if not sub or not sub.is_active:
            d.status = "DEAD_LETTER"
            d.next_attempt_at = None
            continue
        _attempt(db, d, sub)
        n += 1
    db.commit()
    return n


def emit_safely(db: Session, organization_id: Optional[int], event_type: str, payload: dict) -> None:
    """Wrapper that NEVER raises — for use at emit sites inside business
    flows. Webhook failures must not break course completion / cert issue."""
    if not organization_id:
        return
    try:
        emit_event(db, organization_id, event_type, payload)
    except Exception as e:
        logger.exception("webhook emit failed (event=%s org=%s): %s",
                         event_type, organization_id, e)
