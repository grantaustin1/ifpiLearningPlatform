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
from models import LifecycleStage, Organization, PasswordResetToken, Person, RefreshToken, User, UserRole


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

    # ── Password change (self-service) ──────────────────────────────
    def change_password(self, user_id: int, current_password: str,
                        new_password: str) -> None:
        """Iter 32 — used by /api/auth/change-password.
        Verifies the current password before setting the new one.
        Clears `must_change_password` and revokes every existing
        refresh token so the user has to re-login on every device.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.password_hash:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=400,
                                detail="Current password is incorrect")
        if len(new_password) < 8:
            raise HTTPException(status_code=400,
                                detail="New password must be at least 8 characters")
        user.password_hash = get_password_hash(new_password)
        user.must_change_password = False
        self.db.commit()
        # Revoke all refresh tokens so sessions on other devices die
        self.revoke_all(user.id)

    # ── Password reset (email-token flow) ──────────────────────────
    def request_password_reset(self, email: str, ip: Optional[str]
                               ) -> Optional[Tuple[User, str]]:
        """Iter 32 — issue a single-use reset token.

        Returns (user, raw_token) if the email matches an active user,
        else None. Callers should NOT reveal to the client whether the
        email existed (enumeration guard) — always respond 200.
        """
        email = (email or "").lower().strip()
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not user.is_active or not user.password_hash:
            return None
        # Invalidate outstanding tokens for this user
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).update({"used_at": datetime.now(timezone.utc)})
        raw = secrets.token_urlsafe(32)
        import hashlib
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        self.db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            requested_ip=(ip or "")[:45] or None,
        ))
        self.db.commit()
        return user, raw

    def consume_password_reset(self, raw_token: str, new_password: str) -> User:
        import hashlib
        if len(new_password) < 8:
            raise HTTPException(status_code=400,
                                detail="Password must be at least 8 characters")
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        row = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash
        ).first()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        if row.used_at is not None:
            raise HTTPException(status_code=400, detail="Token has already been used")
        # Compare in UTC — expires_at is naive UTC in the DB
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if row.expires_at < now:
            raise HTTPException(status_code=400, detail="Token has expired")
        user = self.db.query(User).filter(User.id == row.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Account inactive")
        user.password_hash = get_password_hash(new_password)
        user.must_change_password = False
        user.failed_login_attempts = 0  # unlock any brute-force lockout
        row.used_at = datetime.now(timezone.utc)
        self.db.commit()
        # Revoke all refresh tokens (paranoia: session hijack scenario)
        self.revoke_all(user.id)
        return user
