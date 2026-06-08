"""Background outbox worker.

In stub mode, every email is auto-marked STUB on insert (the worker is a no-op).
In live mode (`BILLING_LIVE_MODE=true` + `ERP360_BASE_URL`), the worker polls
QUEUED messages every few seconds and dispatches them to ERP360's notification
endpoint. Async-ish: requests return immediately; delivery happens in the
background, decoupling slow upstream calls from user-facing latency.
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from apscheduler.schedulers.background import BackgroundScheduler

from core.config import settings
from core.database import SessionLocal
from models import OutboxMessage

logger = logging.getLogger("ifpi.outbox")

_scheduler: Optional[BackgroundScheduler] = None
WORKER_INTERVAL_SECONDS = 5
BATCH_SIZE = 25
MAX_ATTEMPTS = 3


def _dispatch_one(msg: OutboxMessage) -> tuple[str, Optional[str], Optional[str]]:
    """Returns (status, transport_message_id, error). Pure function — caller commits."""
    if not (settings.billing_live_mode and settings.erp360_base_url):
        # Stub mode: just stamp it as STUB and move on
        return "STUB", None, None
    try:
        payload = {
            "to": [{"email": msg.to_email, "name": msg.to_name}],
            "subject": msg.subject, "html": msg.body_html, "text": msg.body_text or "",
            "template": msg.template,
            "metadata": {"ifpi_outbox_id": msg.id, "ifpi_user_id": msg.user_id},
            # Note: attachment bytes are NOT persisted to the row (only metadata).
            # In live mode we re-render on demand if needed; for now we send
            # without the binary blob since the worker doesn't have it.
            "attachments_metadata": msg.attachments or [],
        }
        with httpx.Client(timeout=20) as cli:
            r = cli.post(
                f"{settings.erp360_base_url}/api/notifications/send",
                json=payload,
                headers={"X-Service-Token": settings.erp360_sso_shared_secret},
            )
            r.raise_for_status()
            data = r.json()
        return "SENT", data.get("message_id") or data.get("id"), None
    except Exception as e:
        logger.warning("Outbox dispatch failed for msg %s: %s", msg.id, e)
        return "FAILED", None, str(e)[:1000]


def _tick():
    """One polling tick — drain up to BATCH_SIZE QUEUED rows."""
    with SessionLocal() as db:
        rows = db.query(OutboxMessage).filter(
            OutboxMessage.status == "QUEUED",
        ).order_by(OutboxMessage.id.asc()).limit(BATCH_SIZE).all()
        if not rows:
            return
        for m in rows:
            status, mid, err = _dispatch_one(m)
            m.status = status
            m.transport_message_id = mid
            m.error = err
            m.sent_at = datetime.now(timezone.utc) if status in {"SENT", "STUB"} else None
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
    logger.info("Outbox worker scheduled every %ss", WORKER_INTERVAL_SECONDS)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
