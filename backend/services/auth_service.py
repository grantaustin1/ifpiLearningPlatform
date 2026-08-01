"""Auth service — login, registration, token rotation. Mirrors ERP360 auth pipeline."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

<<<<<<< HEAD
from core.config import settings
=======
>>>>>>> origin/main
from core.role_registry import normalize_role_names
from core.security import (
    create_access_token, create_refresh_token, decode_token,
    get_password_hash, password_needs_rehash, verify_password,
)
from models import (
    AccountDeletionRequest, EmailVerificationToken, LifecycleStage, Organization,
    PasswordResetToken, Person, RefreshToken, User, UserRole,
)


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
            # Iter 33 — self-registered users start UNVERIFIED. A
            # verification email is sent by the /register endpoint after
            # this method returns. Users can still log in — features
            # that require verified email (publishing to marketplace,
            # instructor role elevation, cert issuance for others) gate
            # separately.
            email_verified_at=None,
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

    # ── Iter 33 · Email verification ────────────────────────────────
    def issue_email_verification(self, user: User) -> str:
        """Return the RAW token to embed in the email. Only the hash is
        stored. Any outstanding un-used tokens for this user are
        invalidated."""
        import hashlib
        self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        ).update({"used_at": datetime.now(timezone.utc)})
        raw = secrets.token_urlsafe(32)
        self.db.add(EmailVerificationToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ))
        self.db.commit()
        return raw

    def consume_email_verification(self, raw_token: str) -> User:
        import hashlib
        row = self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        ).first()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid verification token")
        if row.used_at is not None:
            raise HTTPException(status_code=400, detail="Verification link already used")
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if row.expires_at < now_naive:
            raise HTTPException(status_code=400, detail="Verification link expired")
        user = self.db.query(User).filter(User.id == row.user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Account not found")
        user.email_verified_at = datetime.now(timezone.utc)
        row.used_at = datetime.now(timezone.utc)
        self.db.commit()
        return user

    # ── Iter 33 · GDPR data export ──────────────────────────────────
    def export_user_data(self, user_id: int) -> dict:
        """Return a JSON-serialisable bundle of every piece of PII held
        about this user. Covers profile, enrollments, exam attempts,
        certificates, notifications, and audit records. Frontend
        streams this as a downloadable file.
        """
        from models import (AuditLog, Certificate, Enrollment, ExamAttempt,
                            Notification, RefreshToken as RT)
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        def _iso(dt):
            return dt.isoformat() if dt else None

        return {
            "export_generated_at": datetime.now(timezone.utc).isoformat(),
            "export_format_version": "1.0",
            "profile": {
                "id": user.id, "email": user.email, "name": user.name,
                "organization_id": user.organization_id,
                "points": user.points, "cohort": user.cohort,
                "created_at": _iso(user.created_at),
                "last_login_at": _iso(user.last_login_at),
                "email_verified_at": _iso(user.email_verified_at),
                "must_change_password": bool(user.must_change_password),
                "streak_digest_enabled": bool(user.streak_digest_enabled),
                "roles": [ur.role for ur in user.user_roles],
            },
            "enrollments": [{
                "course_id": e.course_id, "status": str(e.status),
                "progress": e.progress, "enrolled_at": _iso(e.enrolled_at),
                "completed_at": _iso(e.completed_at),
            } for e in self.db.query(Enrollment).filter(
                Enrollment.user_id == user_id).all()],
            "exam_attempts": [{
                "exam_id": a.exam_id, "score": a.score,
                "passed": a.passed, "started_at": _iso(a.started_at),
                "completed_at": _iso(a.completed_at),
            } for a in self.db.query(ExamAttempt).filter(
                ExamAttempt.user_id == user_id).all()],
            "certificates": [{
                "id": c.id, "code": c.code, "type": str(c.type),
                "course_id": c.course_id, "score": c.score,
                "issued_at": _iso(c.issued_at),
                "revoked_at": _iso(c.revoked_at),
                "revoked_reason": c.revoked_reason,
            } for c in self.db.query(Certificate).filter(
                Certificate.user_id == user_id).all()],
            "notifications": [{
                "type": n.type, "title": n.title, "message": n.message,
                "is_read": bool(n.is_read),
                "created_at": _iso(n.created_at),
            } for n in self.db.query(Notification).filter(
                Notification.user_id == user_id).all()],
            "audit_records": [{
                "action": r.action, "target_type": r.target_type,
                "target_id": r.target_id, "created_at": _iso(r.created_at),
            } for r in self.db.query(AuditLog).filter(
                AuditLog.actor_user_id == user_id
            ).limit(500).all()],
            "active_sessions": self.db.query(RT).filter(
                RT.user_id == user_id,
                RT.revoked_at.is_(None), RT.consumed_at.is_(None),
            ).count(),
        }

    # ── Iter 33 · Account self-deletion (GDPR Right to Erasure) ─────
    def request_account_deletion(self, user_id: int,
                                 ip: Optional[str]) -> str:
        """Two-step deletion. Returns a plaintext code the user must
        POST back (via email) to confirm. Codes are 6-digit for easy
        typing; we only persist the SHA-256 hash."""
        import hashlib
        # Invalidate outstanding requests
        self.db.query(AccountDeletionRequest).filter(
            AccountDeletionRequest.user_id == user_id,
            AccountDeletionRequest.confirmed_at.is_(None),
        ).delete()
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.db.add(AccountDeletionRequest(
            user_id=user_id,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            requested_ip=(ip or "")[:45] or None,
        ))
        self.db.commit()
        return code

    def confirm_account_deletion(self, user_id: int, code: str) -> None:
        """Anonymise the user row + revoke sessions. Not a hard delete
        — certs / audit records / enrollments still reference the row
        via FKs. Anonymisation swaps every PII field."""
        import hashlib
        row = self.db.query(AccountDeletionRequest).filter(
            AccountDeletionRequest.user_id == user_id,
            AccountDeletionRequest.code_hash == hashlib.sha256(code.encode()).hexdigest(),
            AccountDeletionRequest.confirmed_at.is_(None),
        ).order_by(AccountDeletionRequest.id.desc()).first()
        if not row:
            raise HTTPException(status_code=400,
                                detail="Invalid or expired confirmation code")
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if row.expires_at < now_naive:
            raise HTTPException(status_code=400,
                                detail="Confirmation code has expired")

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Anonymise every PII field. Preserve FK integrity by keeping
        # the row itself + preserving the ID for downstream references.
        user.email = f"deleted-{user.id}@anon.invalid"
        user.name = "Deleted User"
        user.password_hash = None
        user.is_active = False
        user.deleted_at = datetime.now(timezone.utc)
        user.totp_secret_enc = None
        user.totp_enabled_at = None
        user.totp_recovery_codes = []
        # Anonymise Person row if it exists
        person = self.db.query(Person).filter(Person.user_id == user_id).first()
        if person:
            person.email = user.email
            person.name = user.name
            person.phone = None
        row.confirmed_at = datetime.now(timezone.utc)
        # Nuke all pending reset/verification tokens
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id).delete()
        self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user_id).delete()
        self.db.commit()
        self.revoke_all(user_id)
