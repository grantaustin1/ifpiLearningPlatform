"""SSO bridge service — stubbed in v1, enabled via SSO_ENABLED=true once ERP360 is wired.

Two flows:
1. INBOUND  — ERP360 mints a short-lived JWT, redirects to /api/auth/sso-exchange?token=...
              We verify with ERP360_SSO_SHARED_SECRET, JIT-provision the IFPI user.
2. OUTBOUND — (future) IFPI can ask ERP360 for the current user's data.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from core.config import settings
from core.role_registry import normalize_role_names
from models import LifecycleStage, Organization, Person, User, UserRole

logger = logging.getLogger(__name__)

ERP360_TO_IFPI_ROLE = {
    "OWNER":          "ADMIN",
    "PLATFORM_ADMIN": "SUPER_ADMIN",
    "SUPER_ADMIN":    "SUPER_ADMIN",
    "MANAGER":        "ADMIN",
    "HEAD_OF_ADMIN":  "ADMIN",
    "HR_ADMIN":       "INSTRUCTOR",
    "TRAINER":        "INSTRUCTOR",
    "ACCOUNTANT":     "BILLING_VIEWER",
}


class SSOService:
    def __init__(self, db: Session):
        self.db = db

    def is_enabled(self) -> bool:
        return settings.sso_enabled and bool(settings.erp360_sso_shared_secret)

    def verify_inbound_token(self, token: str) -> dict:
        if not self.is_enabled():
            raise HTTPException(status_code=503, detail="SSO is not enabled")
        try:
            payload = jwt.decode(
                token, settings.erp360_sso_shared_secret,
                algorithms=["HS256"], audience="ifpi-lms",
            )
        except JWTError as e:
            logger.warning("SSO token verify failed: %s", e)
            raise HTTPException(status_code=401, detail="Invalid SSO token")
        return payload

    def jit_provision(self, claims: dict) -> User:
        """Create or update the IFPI user from ERP360 claims, then return it."""
        erp_user_id = claims.get("sub")
        email = (claims.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(status_code=400, detail="SSO token missing email")

        org = self.db.query(Organization).order_by(Organization.id.asc()).first()
        if not org:
            raise HTTPException(status_code=500, detail="No academy configured")

        user: Optional[User] = None
        if erp_user_id:
            user = self.db.query(User).filter(
                User.erp360_user_id == int(erp_user_id),
            ).first()
        if not user:
            user = self.db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email, name=claims.get("name"),
                organization_id=org.id, is_active=True,
                erp360_user_id=int(erp_user_id) if erp_user_id else None,
            )
            self.db.add(user)
            self.db.flush()
        else:
            user.email = email
            user.name = claims.get("name") or user.name
            user.erp360_user_id = int(erp_user_id) if erp_user_id else user.erp360_user_id
            user.is_active = True

        # Person identity row — upsert with erp360_person_id from claim if present
        person = self.db.query(Person).filter(Person.user_id == user.id).first()
        erp_person_id = claims.get("person_id") or claims.get("erp360_person_id")
        if not person:
            person = Person(
                user_id=user.id, organization_id=org.id,
                email=email, name=claims.get("name"),
                lifecycle_stage=LifecycleStage.LEARNER,
                source="sso_erp360",
                erp360_person_id=int(erp_person_id) if erp_person_id else None,
            )
            self.db.add(person)
        else:
            person.email = email
            person.name = claims.get("name") or person.name
            person.lifecycle_stage = LifecycleStage.LEARNER
            if erp_person_id:
                person.erp360_person_id = int(erp_person_id)

        # Map roles ERP360 → IFPI
        incoming_erp_roles = normalize_role_names(claims.get("roles") or [])
        ifpi_roles = {ERP360_TO_IFPI_ROLE.get(r, "LEARNER") for r in incoming_erp_roles} or {"LEARNER"}

        # Replace role rows
        self.db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        for r in ifpi_roles:
            self.db.add(UserRole(user_id=user.id, role=r))

        self.db.commit()
        self.db.refresh(user)
        return user
