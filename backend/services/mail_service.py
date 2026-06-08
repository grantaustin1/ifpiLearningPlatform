"""Mail service.

Modes (via env):
- `stub`   — default. Persists to `OutboxMessage` only; no real send. Visible
             to admins via `/api/admin/outbox`. Perfect for v1.
- `erp360` — when SSO+billing are live, also POSTs to ERP360's notification
             transport. ERP360 owns SMTP/SendGrid/etc.

Public API is the same regardless of mode — callers always go through
`send_email(...)`.
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from models import OutboxMessage

logger = logging.getLogger(__name__)


class MailService:
    def __init__(self, db: Session):
        self.db = db

    def _transport(self) -> str:
        if settings.billing_live_mode and settings.erp360_base_url:
            return "erp360"
        return "stub"

    def send_email(
        self, *, to_email: str, subject: str, body_html: str,
        body_text: Optional[str] = None, to_name: Optional[str] = None,
        template: Optional[str] = None,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        attachments: Optional[List[dict]] = None,
    ) -> OutboxMessage:
        """Always returns the persisted OutboxMessage so the caller can show
        a "queued / sent" status in the UI."""
        transport = self._transport()
        msg = OutboxMessage(
            organization_id=organization_id, user_id=user_id,
            to_email=to_email, to_name=to_name, subject=subject,
            body_text=body_text or "", body_html=body_html,
            attachments=[{"filename": a["filename"], "mime": a.get("mime", "application/pdf")}
                         for a in (attachments or [])],
            template=template, transport=transport, status="QUEUED",
        )
        self.db.add(msg)
        self.db.flush()

        if transport == "stub":
            msg.status = "STUB"
            msg.sent_at = datetime.now(timezone.utc)
            logger.info("[MAIL STUB] To=%s Subject=%s (id=%s)", to_email, subject, msg.id)
            self.db.commit()
            return msg

        # erp360 transport
        try:
            payload = {
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
                "html": body_html, "text": body_text or "",
                "template": template,
                "metadata": {"ifpi_outbox_id": msg.id, "ifpi_user_id": user_id},
                "attachments": [
                    {"filename": a["filename"],
                     "content_base64": base64.b64encode(a["content"]).decode("ascii"),
                     "mime": a.get("mime", "application/pdf")}
                    for a in (attachments or []) if "content" in a
                ],
            }
            with httpx.Client(timeout=20) as cli:
                r = cli.post(
                    f"{settings.erp360_base_url}/api/notifications/send",
                    json=payload,
                    headers={"X-Service-Token": settings.erp360_sso_shared_secret},
                )
                r.raise_for_status()
                data = r.json()
            msg.status = "SENT"
            msg.transport_message_id = data.get("message_id") or data.get("id")
            msg.sent_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.exception("ERP360 mail send failed: %s", e)
            msg.status = "FAILED"
            msg.error = str(e)[:1000]
        self.db.commit()
        return msg
