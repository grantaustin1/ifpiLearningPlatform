"""SSO bridge service — stubbed in v1, enabled via SSO_ENABLED=true once ERP360 is wired.

Two flows:
1. INBOUND  — ERP360 mints a short-lived JWT, redirects to /api/auth/sso-exchange?token=...
              We verify with ERP360_SSO_SHARED_SECRET, JIT-provision the IFPI user.
2. OUTBOUND — (future) IFPI can ask ERP360 for the current user's data.

Token contract (claims ERP360 MUST include):
  - iss   = "erp360"
  - aud   = "ifpi-lms"
  - sub   = ERP360 user id (string or int)
  - email = user email
  - exp   = unix ts (jose enforces; we add a max-age sanity check too)
  - iat   = unix ts (we reject tokens older than 5 min)
  - jti   = unique token id (we maintain an in-memory replay-prevention cache)
  - name  = user display name (optional)
  - roles = list of ERP360 role strings (e.g. ["MANAGER", "TRAINER"])
  - person_id / erp360_person_id = optional CRM person id
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from models import LifecycleStage, Organization, Person, SsoJtiSeen, User, UserRole

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
    "BILLING_USER":   "BILLING_VIEWER",
}

# Maximum age (in seconds) of an inbound SSO token. ERP360 should be minting
# tokens with a 5-min exp; we enforce iat freshness on top of jose's exp check
# to defend against badly-skewed clocks producing very-old tokens.
MAX_TOKEN_AGE_SECONDS = 300

# Replay-protection TTL — purge SsoJtiSeen rows older than this on each new
# token. 10 min comfortably overlaps the MAX_TOKEN_AGE window above.
_REPLAY_TTL_SECONDS = 600


def _check_replay(db: Session, jti: str) -> None:
    """Raises 401 if jti has been seen before. Multi-process safe via the
    `sso_jti_seen` SQL table — survives across worker pods, unlike the
    previous in-memory dict.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    # Opportunistic GC of expired rows. Tiny query — cheap even at scale
    # because the table is bounded by traffic over the last ~10 min.
    cutoff = now - timedelta(seconds=_REPLAY_TTL_SECONDS)
    db.query(SsoJtiSeen).filter(SsoJtiSeen.seen_at < cutoff).delete()

    if db.query(SsoJtiSeen).filter(SsoJtiSeen.jti == jti).first():
        raise HTTPException(status_code=401, detail="SSO token already used (replay)")
    db.add(SsoJtiSeen(jti=jti, seen_at=now))
    try:
        # Commit immediately so a later rollback in jit_provision can't
        # erase the replay marker and re-open the token for reuse.
        db.commit()
    except IntegrityError:
        # Race: another worker just inserted the same jti. That's a replay.
        db.rollback()
        raise HTTPException(status_code=401, detail="SSO token already used (replay)")


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
                options={"require_exp": True, "require_iat": True, "require_sub": True},
            )
        except JWTError as e:
            logger.warning("SSO token verify failed: %s", e)
            raise HTTPException(status_code=401, detail=f"Invalid SSO token: {type(e).__name__}")
        # Issuer must be erp360 — defends against tokens minted for another audience reuser
        if payload.get("iss") != "erp360":
            raise HTTPException(status_code=401, detail="Invalid SSO token issuer")
        # iat freshness — extra defence beyond exp
        iat = payload.get("iat")
        if isinstance(iat, (int, float)) and (time.time() - iat) > MAX_TOKEN_AGE_SECONDS:
            raise HTTPException(status_code=401, detail="SSO token too old")
        # Replay protection requires jti
        jti = payload.get("jti")
        if not jti or not isinstance(jti, str):
            raise HTTPException(status_code=401, detail="SSO token missing jti")
        _check_replay(self.db, jti)
        return payload

    def jit_provision(self, claims: dict) -> tuple[User, bool]:
        """Create or update the IFPI user from ERP360 claims.

        Returns (user, created) — `created` is True when this is the first
        time IFPI has seen this user (i.e. JIT just provisioned them).
        """
        erp_user_id = claims.get("sub")
        email = (claims.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(status_code=400, detail="SSO token missing email")

        org = self.db.query(Organization).order_by(Organization.id.asc()).first()
        if not org:
            raise HTTPException(status_code=500, detail="No academy configured")

        user: Optional[User] = None
        if erp_user_id:
            try:
                _erp_id = int(erp_user_id)
            except (TypeError, ValueError):
                _erp_id = None
            if _erp_id is not None:
                user = self.db.query(User).filter(User.erp360_user_id == _erp_id).first()
        else:
            _erp_id = None

        if not user:
            user = self.db.query(User).filter(User.email == email).first()

        created = user is None
        if created:
            user = User(
                email=email, name=claims.get("name"),
                organization_id=org.id, is_active=True,
                erp360_user_id=_erp_id,
            )
            self.db.add(user)
            self.db.flush()
        else:
            user.email = email
            user.name = claims.get("name") or user.name
            if _erp_id is not None:
                user.erp360_user_id = _erp_id
            user.is_active = True

        # Person identity row — upsert with erp360_person_id from claim if present
        person = self.db.query(Person).filter(Person.user_id == user.id).first()
        erp_person_id_raw = claims.get("person_id") or claims.get("erp360_person_id")
        try:
            erp_person_id = int(erp_person_id_raw) if erp_person_id_raw is not None else None
        except (TypeError, ValueError):
            erp_person_id = None
        if not person:
            person = Person(
                user_id=user.id, organization_id=org.id,
                email=email, name=claims.get("name"),
                lifecycle_stage=LifecycleStage.LEARNER,
                source="sso_erp360",
                erp360_person_id=erp_person_id,
            )
            self.db.add(person)
        else:
            person.email = email
            person.name = claims.get("name") or person.name
            person.lifecycle_stage = LifecycleStage.LEARNER
            if erp_person_id is not None:
                person.erp360_person_id = erp_person_id

        # Map roles ERP360 → IFPI. We deliberately do NOT pre-normalise here;
        # ERP360 ships its own role vocabulary (TRAINER, MANAGER, ACCOUNTANT…)
        # and we want our explicit map to win over the generic alias table in
        # `core.role_registry.normalize_role_name`.
        raw_roles = claims.get("roles") or []
        if isinstance(raw_roles, str):
            raw_roles = [raw_roles]
        ifpi_roles = set()
        for r in raw_roles:
            if not r or not isinstance(r, str):
                continue
            key = r.strip().upper().replace(" ", "_").replace("-", "_")
            ifpi_roles.add(ERP360_TO_IFPI_ROLE.get(key, "LEARNER"))
        if not ifpi_roles:
            ifpi_roles = {"LEARNER"}

        # Replace role rows
        self.db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        for r in ifpi_roles:
            self.db.add(UserRole(user_id=user.id, role=r))

        self.db.commit()
        self.db.refresh(user)
        return user, created
