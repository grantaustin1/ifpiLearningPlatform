"""Auth service — login, registration, token rotation. Mirrors ERP360 auth pipeline."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from core.role_registry import normalize_role_names
from core.security import (
    create_access_token, create_refresh_token, decode_token,
    get_password_hash, password_needs_rehash, verify_password,
)
from models import LifecycleStage, Organization, Person, RefreshToken, User, UserRole


MAX_FAILED_ATTEMPTS = 5


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    # ── Registration ──────────────────────────────────────────────────
    def register(self, email: str, password: str, name: str,
                 organization_id: Optional[int] = None) -> User:
        email = email.lower().strip()
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Default to the first / default academy
        if organization_id is None:
            org = self.db.query(Organization).order_by(Organization.id.asc()).first()
            if not org:
                raise HTTPException(status_code=500, detail="No academy configured")
            organization_id = org.id

        user = User(
            email=email,
            password_hash=get_password_hash(password),
            name=name,
            organization_id=organization_id,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        # CRITICAL: self-registration is LEARNER only. Admins are invite-only.
        self.db.add(UserRole(user_id=user.id, role="LEARNER"))
        # Auto-create Person identity row (mirrors ERP360 pattern)
        self.db.add(Person(
            user_id=user.id, organization_id=organization_id,
            email=email, name=name, lifecycle_stage=LifecycleStage.LEARNER,
            source="self_register",
        ))
        self.db.commit()
        self.db.refresh(user)
        return user

    # ── Login ─────────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> User:
        email = email.lower().strip()
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not user.password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account is locked")
        if not verify_password(password, user.password_hash):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.is_active = False
            self.db.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Reset failed attempts, update timestamps, opportunistic rehash
        user.failed_login_attempts = 0
        user.last_login_at = datetime.now(timezone.utc)
        if password_needs_rehash(user.password_hash):
            user.password_hash = get_password_hash(password)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ── Token issuance ───────────────────────────────────────────────
    def issue_tokens(self, user: User) -> Tuple[str, str]:
        roles = normalize_role_names([ur.role for ur in user.user_roles]) or ["LEARNER"]
        claims = {
            "email": user.email,
            "name": user.name,
            "org_id": user.organization_id,
            "roles": roles,
        }
        access = create_access_token(user.id, claims=claims)

        family_id = uuid.uuid4().hex
        refresh = create_refresh_token(user.id, family_id=family_id)
        # Persist the refresh row so we can detect reuse-of-consumed
        payload = decode_token(refresh)
        jti = secrets.token_hex(16)
        self.db.add(RefreshToken(
            user_id=user.id,
            family_id=family_id,
            jti=jti,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        ))
        self.db.commit()
        return access, refresh

    # ── Token rotation ───────────────────────────────────────────────
    def rotate_refresh(self, refresh_token: str) -> Tuple[str, str, User]:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Wrong token type")

        user_id = int(payload["sub"])
        family_id = payload.get("fam")
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive")

        # Detect reuse: any token in this family already consumed → revoke whole family
        consumed = self.db.query(RefreshToken).filter(
            RefreshToken.family_id == family_id,
            RefreshToken.consumed_at.isnot(None),
        ).first()
        if consumed:
            self.db.query(RefreshToken).filter(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": datetime.now(timezone.utc)})
            self.db.commit()
            raise HTTPException(status_code=401, detail="Refresh token reuse detected")

        # Mark all active tokens in the family consumed, issue a new one
        self.db.query(RefreshToken).filter(
            RefreshToken.family_id == family_id, RefreshToken.consumed_at.is_(None),
        ).update({"consumed_at": datetime.now(timezone.utc)})

        return *self.issue_tokens(user), user

    def revoke_all(self, user_id: int) -> None:
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": datetime.now(timezone.utc)})
        self.db.commit()
