"""Mail service.

Caller-facing API is `send_email(...)`. It ALWAYS just queues a row in the
`outbox_messages` table (status='QUEUED'). A background worker
(`services/outbox_worker.py`) drains the queue every few seconds and
dispatches:

- In `stub` mode (default) — marks each row STUB. Visible to admins via
  `/api/admin/outbox`. Perfect for v1.
- In `erp360` mode (when `BILLING_LIVE_MODE=true` + `ERP360_BASE_URL` are set)
  — POSTs the row to ERP360's notification endpoint.

This means the request that emits an email returns immediately — slow upstream
mail providers can't impact user-facing latency.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from models import OutboxMessage

logger = logging.getLogger(__name__)


class MailService:
    def __init__(self, db: Session):
        self.db = db

    def _transport(self) -> str:
        return "erp360" if (settings.billing_live_mode and settings.erp360_base_url) else "stub"

    def send_email(
        self, *, to_email: str, subject: str, body_html: str,
        body_text: Optional[str] = None, to_name: Optional[str] = None,
        template: Optional[str] = None,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        attachments: Optional[List[dict]] = None,
    ) -> OutboxMessage:
        """Queues the email. Returns the persisted OutboxMessage immediately;
        actual delivery is asynchronous (see `outbox_worker.py`)."""
        msg = OutboxMessage(
            organization_id=organization_id, user_id=user_id,
            to_email=to_email, to_name=to_name, subject=subject,
            body_text=body_text or "", body_html=body_html,
            attachments=[{"filename": a["filename"], "mime": a.get("mime", "application/pdf")}
                         for a in (attachments or [])],
            template=template, transport=self._transport(), status="QUEUED",
        )
        self.db.add(msg)
        self.db.flush()
        logger.info("[MAIL QUEUED] id=%s to=%s subject=%s", msg.id, to_email, subject)
        # Caller commits — keeping this transactional with whatever else
        # they're doing (e.g. cert issuance).
        return msg
