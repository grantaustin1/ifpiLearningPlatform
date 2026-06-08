"""Background outbox worker with exponential backoff + dead-letter handling."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from apscheduler.schedulers.background import BackgroundScheduler

from core.config import settings
from core.database import SessionLocal
from models import Organization, OutboxMessage

logger = logging.getLogger("ifpi.outbox")

_scheduler: Optional[BackgroundScheduler] = None
WORKER_INTERVAL_SECONDS = 5
BATCH_SIZE = 25
MAX_ATTEMPTS = 3
# Exponential backoff: 30s, 5min, 30min before going to dead-letter
BACKOFF_SECONDS = [30, 300, 1800]


def _dispatch_one(msg: OutboxMessage) -> tuple[str, Optional[str], Optional[str]]:
    """Returns (status, transport_message_id, error).

    Priority order:
    1. Per-tenant SMTP — when the message's org has smtp_host configured
       we deliver directly via that server.
    2. ERP360 bridge — when BILLING_LIVE_MODE + ERP360_BASE_URL are set.
    3. Stub — log only, mark STUB.
    """
    # 1) Per-tenant SMTP
    if msg.organization_id:
        with SessionLocal() as _db:
            org = _db.query(Organization).filter(Organization.id == msg.organization_id).first()
            if org and org.smtp_host and org.smtp_from_email:
                try:
                    from services.smtp_service import send_via_org_smtp
                    send_via_org_smtp(
                        host=org.smtp_host, port=org.smtp_port or 587,
                        username=org.smtp_username, password_enc=org.smtp_password_enc,
                        use_tls=org.smtp_use_tls if org.smtp_use_tls is not None else True,
                        from_email=org.smtp_from_email, from_name=org.smtp_from_name,
                        to_email=msg.to_email, to_name=msg.to_name,
                        subject=msg.subject, body_html=msg.body_html or "",
                        body_text=msg.body_text or "",
                    )
                    return "SENT", None, None
                except Exception as e:
                    logger.warning("Per-tenant SMTP failed for msg %s: %s", msg.id, e)
                    return "FAILED", None, f"smtp: {str(e)[:900]}"
    # 2) ERP360 bridge / 3) Stub
    if not (settings.billing_live_mode and settings.erp360_base_url):
        return "STUB", None, None
    try:
        payload = {
            "to": [{"email": msg.to_email, "name": msg.to_name}],
            "subject": msg.subject, "html": msg.body_html, "text": msg.body_text or "",
            "template": msg.template,
            "metadata": {"ifpi_outbox_id": msg.id, "ifpi_user_id": msg.user_id},
            "attachments_metadata": msg.attachments or [],
        }
        # Sign the request body for downstream HMAC verification
        import json
        from routers.iter5 import sign_outgoing_payload
        raw = json.dumps(payload).encode("utf-8")
        headers = sign_outgoing_payload(raw) or {"X-Service-Token": settings.erp360_sso_shared_secret}
        with httpx.Client(timeout=20) as cli:
            r = cli.post(
                f"{settings.erp360_base_url}/api/notifications/send",
                content=raw, headers={**headers, "Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
        return "SENT", data.get("message_id") or data.get("id"), None
    except Exception as e:
        logger.warning("Outbox dispatch failed for msg %s: %s", msg.id, e)
        return "FAILED", None, str(e)[:1000]


def _tick():
    """One polling tick. Picks up:
    - QUEUED messages whose next_attempt_at has passed (or is null)
    - FAILED messages eligible for retry under backoff
    Anything that hits MAX_ATTEMPTS becomes DEAD_LETTER.
    """
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = db.query(OutboxMessage).filter(
            OutboxMessage.status.in_(("QUEUED", "FAILED")),
            (OutboxMessage.next_attempt_at.is_(None)) | (OutboxMessage.next_attempt_at <= now),
        ).order_by(OutboxMessage.id.asc()).limit(BATCH_SIZE).all()
        if not rows:
            return
        for m in rows:
            m.attempt_count = (m.attempt_count or 0) + 1
            status, mid, err = _dispatch_one(m)
            if status in {"SENT", "STUB"}:
                m.status = status
                m.transport_message_id = mid
                m.error = None
                m.sent_at = now
                m.next_attempt_at = None
            else:
                m.error = err
                if m.attempt_count >= MAX_ATTEMPTS:
                    m.status = "DEAD_LETTER"
                    m.next_attempt_at = None
                else:
                    m.status = "FAILED"
                    idx = min(m.attempt_count - 1, len(BACKOFF_SECONDS) - 1)
                    m.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[idx])
        db.commit()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = BackgroundScheduler(daemon=True, timezone="UTC")
    sched.add_job(
        _tick, "interval", seconds=WORKER_INTERVAL_SECONDS,
        id="outbox_drain", max_instances=1, coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info("Outbox worker scheduled every %ss (max %s attempts)",
                WORKER_INTERVAL_SECONDS, MAX_ATTEMPTS)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
