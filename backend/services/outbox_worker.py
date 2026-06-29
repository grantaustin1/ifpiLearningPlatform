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


def _cohort_tick():
    """Periodic cohort milestone checker. Independent from the outbox drain
    so it runs at a lower cadence and never blocks email delivery."""
    import time
    started = time.monotonic()
    try:
        with SessionLocal() as db:
            from services.cohort_celebrations import check_cohorts
            fired = check_cohorts(db)
            if fired:
                logger.info("Fired %s cohort celebration(s) this tick", fired)
    except Exception as e:
        logger.exception("cohort celebration tick failed: %s", e)
    elapsed = time.monotonic() - started
    if elapsed > 30:
        logger.warning("cohort tick took %.1fs — consider increasing interval", elapsed)


def _digest_tick():
    """Weekly cohort digest job. Fires every Monday 09:00 UTC; the service
    self-skips orgs sent in the past 6 days, so a misfire on Mon is harmless."""
    try:
        with SessionLocal() as db:
            from services.cohort_digest import send_weekly_digests
            total = send_weekly_digests(db)
            if total:
                logger.info("Queued %s cohort-digest email(s)", total)
    except Exception as e:
        logger.exception("cohort digest tick failed: %s", e)


def _webhook_retry_tick():
    """Retry FAILED outgoing webhook deliveries whose next_attempt_at is due."""
    try:
        with SessionLocal() as db:
            from services.webhook_service import drain_failed
            n = drain_failed(db)
            if n:
                logger.info("Retried %s webhook delivery row(s)", n)
    except Exception as e:
        logger.exception("webhook retry tick failed: %s", e)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = BackgroundScheduler(daemon=True, timezone="UTC")
    sched.add_job(
        _tick, "interval", seconds=WORKER_INTERVAL_SECONDS,
        id="outbox_drain", max_instances=1, coalesce=True,
    )
    sched.add_job(
        _cohort_tick, "interval", seconds=60,  # check once a minute
        id="cohort_celebrations", max_instances=1, coalesce=True,
        misfire_grace_time=120,
    )
    sched.add_job(
        _digest_tick, "cron", day_of_week="mon", hour=9, minute=0,
        id="cohort_weekly_digest", max_instances=1, coalesce=True,
        misfire_grace_time=3600,
    )
    sched.add_job(
        _webhook_retry_tick, "interval", seconds=30,
        id="webhook_retry", max_instances=1, coalesce=True,
        misfire_grace_time=120,
    )
    sched.start()
    _scheduler = sched
    logger.info("Outbox worker scheduled every %ss (max %s attempts), "
                "cohort celebrator every 60s, weekly digest Mon 09:00 UTC, "
                "webhook retry every 30s",
                WORKER_INTERVAL_SECONDS, MAX_ATTEMPTS)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
