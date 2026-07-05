"""Iter 30r — Live email delivery diagnostics.

Admin-only endpoint to verify SMTP settings are working. Sends a small
test email via the same code path as the outbox worker. Useful when
setting up per-tenant SMTP or when validating a new system-level relay.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from models import Organization, OutboxMessage
from services import audit_service

router = APIRouter(prefix="/api/admin/email", tags=["Email diagnostics"])


class TestEmailIn(BaseModel):
    to_email: EmailStr
    subject: str = Field(default="[IFPI] SMTP test", max_length=200)
    use_transport: str = Field(default="auto", pattern="^(auto|per_tenant|system|erp360)$")


class TransportStatus(BaseModel):
    transport: str
    configured: bool
    note: str


@router.get("/transport-status")
def transport_status(current: CurrentUser = Depends(requires_admin()),
                     db: Session = Depends(get_db)) -> dict:
    """Report which delivery transports are active for THIS org, in
    priority order (first match wins)."""
    from core.config import settings
    org = db.query(Organization).filter(
        Organization.id == current.organization_id).first()

    per_tenant_configured = bool(org and org.smtp_host and org.smtp_from_email)
    system_configured = bool(os.environ.get("SYSTEM_SMTP_HOST", "").strip())
    erp360_configured = bool(settings.billing_live_mode
                             and settings.erp360_base_url)

    transports = [
        TransportStatus(
            transport="per_tenant",
            configured=per_tenant_configured,
            note=(f"{org.smtp_host}:{org.smtp_port or 587}" if per_tenant_configured
                  else "Configure via Settings → Branding → SMTP"),
        ),
        TransportStatus(
            transport="system",
            configured=system_configured,
            note=(f"{os.environ.get('SYSTEM_SMTP_HOST')} (env)" if system_configured
                  else "Set SYSTEM_SMTP_HOST / SYSTEM_SMTP_PORT / SYSTEM_SMTP_USERNAME / SYSTEM_SMTP_PASSWORD env vars"),
        ),
        TransportStatus(
            transport="erp360",
            configured=erp360_configured,
            note=(f"{settings.erp360_base_url}" if erp360_configured
                  else "Set BILLING_LIVE_MODE=1 + ERP360_BASE_URL"),
        ),
    ]

    active = next((t.transport for t in transports if t.configured), "stub")
    return {"active_transport": active,
            "transports": [t.model_dump() for t in transports]}


@router.post("/send-test")
def send_test_email(body: TestEmailIn, request: Request,
                    current: CurrentUser = Depends(requires_admin()),
                    db: Session = Depends(get_db)) -> dict:
    """Queue a test email and dispatch it synchronously so the admin
    gets immediate feedback (STUB / SENT / FAILED + error)."""
    from services.outbox_worker import _dispatch_one

    # Build the outbox message but DON'T commit yet — dispatch first
    msg = OutboxMessage(
        organization_id=current.organization_id,
        user_id=current.id,
        to_email=body.to_email,
        to_name=None,
        subject=body.subject,
        body_html=(
            "<h2 style='font:600 18px system-ui'>SMTP test</h2>"
            "<p style='font:14px system-ui'>If you're reading this, your IFPI "
            "email pipeline is working.</p>"
            f"<p style='font:12px system-ui;color:#64748b'>Requested by "
            f"{current.email} at {os.environ.get('HOSTNAME', 'unknown host')}.</p>"
        ),
        body_text="SMTP test — if you're reading this, your IFPI email pipeline is working.",
        template="smtp_test",
    )
    db.add(msg)
    db.flush()

    try:
        status, transport_id, err = _dispatch_one(msg)
    except Exception as e:
        status, transport_id, err = "FAILED", None, str(e)[:500]
    msg.status = status
    if transport_id:
        msg.transport_message_id = transport_id
    if err:
        msg.last_error = err

    audit_service.record(db, current, "EMAIL_TEST_SENT",
                         target_type="outbox", target_id=str(msg.id),
                         metadata={"to": body.to_email, "status": status},
                         request=request)
    db.commit()

    if status == "FAILED":
        raise HTTPException(status_code=502,
                            detail=f"Send failed: {err}")

    return {"outbox_id": msg.id, "status": status,
            "transport_message_id": transport_id,
            "note": ("Delivered — check the inbox." if status == "SENT"
                     else "STUB mode: email was logged but not delivered. "
                          "Configure per_tenant or system SMTP to send real emails.")}
