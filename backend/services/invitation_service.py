"""Invitation service — admins invite by email with a role; recipient sets password."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.role_registry import (
    ADMIN_ROLES, CANONICAL_ROLE_SET, normalize_role_name,
)
from core.security import get_password_hash
from models import (
    Invitation, LifecycleStage, Organization, Person, User, UserRole,
)
from services.mail_service import MailService

INVITE_TTL_DAYS = 14
ALLOWED_INVITE_ROLES = {"ADMIN", "INSTRUCTOR", "BILLING_VIEWER", "LEARNER"}


class InvitationService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, organization_id: int, invited_by_id: int,
               email: str, name: Optional[str], role: str,
               app_base_url: str, cohort: Optional[str] = None) -> Invitation:
        email = (email or "").lower().strip()
        if not email:
            raise HTTPException(status_code=400, detail="email is required")
        canonical_role = normalize_role_name(role)
        if canonical_role not in ALLOWED_INVITE_ROLES:
            raise HTTPException(status_code=400, detail=f"Role must be one of {sorted(ALLOWED_INVITE_ROLES)}")

        # Block if a user with that email already exists in this org
        existing_user = self.db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400,
                                detail="A user with this email already exists")

        # If an active (un-accepted, un-revoked, un-expired) invite already
        # exists, revoke it before issuing a new one (so admins can re-send).
        now = datetime.now(timezone.utc)
        self.db.query(Invitation).filter(
            Invitation.organization_id == organization_id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        ).update({"revoked_at": now})

        token = secrets.token_urlsafe(32)
        inv = Invitation(
            organization_id=organization_id, email=email, name=name,
            role=canonical_role, token=token, invited_by_id=invited_by_id,
            cohort=cohort,
            expires_at=now + timedelta(days=INVITE_TTL_DAYS),
        )
        self.db.add(inv)
        self.db.flush()

        # Send the invite via the mail service (stub mode persists to outbox)
        accept_url = f"{app_base_url.rstrip('/')}/accept-invite/{token}"
        org_name = self._org_name(organization_id)
        body_html = _invite_email_html(
            org_name=org_name, role=canonical_role,
            accept_url=accept_url, ttl_days=INVITE_TTL_DAYS,
        )
        MailService(self.db).send_email(
            to_email=email, to_name=name, subject=f"You're invited to {org_name}",
            body_html=body_html, template="invitation",
            organization_id=organization_id,
        )
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def _org_name(self, organization_id: int) -> str:
        org = self.db.query(Organization).filter(Organization.id == organization_id).first()
        return org.name if org else "IFPI Learning"

    def lookup(self, token: str) -> Invitation:
        inv = self.db.query(Invitation).filter(Invitation.token == token).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invitation not found")
        if inv.accepted_at:
            raise HTTPException(status_code=400, detail="Invitation already used")
        if inv.revoked_at:
            raise HTTPException(status_code=400, detail="Invitation revoked")
        exp = inv.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Invitation expired")
        return inv

    def accept(self, token: str, password: str, name: Optional[str] = None) -> User:
        inv = self.lookup(token)
        if len(password or "") < 8:
            raise HTTPException(status_code=400, detail="Password must be 8+ characters")
        user = User(
            email=inv.email, name=name or inv.name,
            password_hash=get_password_hash(password),
            organization_id=inv.organization_id, is_active=True,
            cohort=inv.cohort,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserRole(user_id=user.id, role=inv.role))
        self.db.add(Person(
            user_id=user.id, organization_id=inv.organization_id,
            email=inv.email, name=user.name,
            lifecycle_stage=LifecycleStage.LEARNER, source="invitation",
        ))
        inv.accepted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user

    def revoke(self, invitation_id: int, organization_id: int) -> None:
        inv = self.db.query(Invitation).filter(
            Invitation.id == invitation_id,
            Invitation.organization_id == organization_id,
        ).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invitation not found")
        if inv.accepted_at:
            raise HTTPException(status_code=400, detail="Already accepted — cannot revoke")
        inv.revoked_at = datetime.now(timezone.utc)
        self.db.commit()


def _invite_email_html(org_name: str, role: str, accept_url: str, ttl_days: int) -> str:
    role_label = role.replace("_", " ").title()
    return f"""
<!DOCTYPE html><html><body style="font-family: -apple-system, system-ui, sans-serif; background: #f8fafc; padding: 32px;">
  <div style="max-width: 540px; margin: 0 auto; background: white; border-radius: 16px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.05);">
    <h1 style="margin: 0 0 8px; color: #0f172a; font-size: 22px;">You're invited to {org_name}</h1>
    <p style="color: #64748b; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
      You've been invited as <strong>{role_label}</strong>. Click below to set a password and finish creating your account.
    </p>
    <a href="{accept_url}" style="display: inline-block; background: #6366f1; color: white; text-decoration: none; padding: 12px 24px; border-radius: 12px; font-weight: 600; font-size: 14px;">Accept invitation</a>
    <p style="color: #94a3b8; font-size: 12px; margin: 24px 0 0;">This invitation expires in {ttl_days} days. If you didn't expect this, you can safely ignore it.</p>
  </div>
</body></html>
""".strip()
