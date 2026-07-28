"""Iter 30i — TOTP-based 2FA endpoints.

Self-service enable/disable + admin force-disable. The login flow itself
lives in `routers/auth.py` — it dispatches to a challenge here when the
user has 2FA enabled.

Endpoints
---------
- `GET  /api/auth/2fa/status`         — returns {enabled, enabled_at}
- `POST /api/auth/2fa/setup-init`     — generates secret + QR (not yet saved)
- `POST /api/auth/2fa/setup`          — verify code + persist encrypted secret
- `POST /api/auth/2fa/disable`        — self-disable (needs password + code)
- `POST /api/auth/2fa/challenge`      — public, exchange challenge_id + code → LoginResponse
- `POST /api/admin/users/{id}/2fa/disable` — SUPER_ADMIN force-disable
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.security import verify_password
from models import User
from schemas import (
    LoginResponse, TOTPChallengeIn, TOTPDisableIn, TOTPSetupIn,
)
from services import audit_service, totp_service
from services.auth_service import AuthService

logger = logging.getLogger("ifpi.totp")

user_router = APIRouter(prefix="/api/auth/2fa", tags=["2FA"])
admin_router = APIRouter(prefix="/api/admin/users", tags=["2FA Admin"])


# ── Challenge storage (in-memory, 5-min TTL) ───────────────────────────
# For a single-worker deployment. If we move to multi-worker, this
# lifts into Redis with the same interface — the challenge_id is opaque
# from the client's POV.

_CHALLENGE_TTL = 300  # 5 min
_challenges: dict[str, tuple[int, float, int]] = {}
# challenge_id → (user_id, expires_at_epoch, attempt_count)
_MAX_ATTEMPTS = 5


def _gc_challenges() -> None:
    now = time.time()
    for k, (_uid, exp, _n) in list(_challenges.items()):
        if exp < now:
            _challenges.pop(k, None)


def create_challenge(user_id: int) -> tuple[str, int]:
    """Return (challenge_id, expires_in_seconds). Called by /auth/login
    when the user has 2FA enabled."""
    _gc_challenges()
    cid = secrets.token_urlsafe(24)
    _challenges[cid] = (user_id, time.time() + _CHALLENGE_TTL, 0)
    return cid, _CHALLENGE_TTL


def _consume_challenge(challenge_id: str) -> Optional[int]:
    """Increment attempt count and return the user_id if the challenge
    is still valid. Removes the entry after max attempts."""
    _gc_challenges()
    entry = _challenges.get(challenge_id)
    if not entry:
        return None
    user_id, expires, attempts = entry
    if expires < time.time():
        _challenges.pop(challenge_id, None)
        return None
    if attempts >= _MAX_ATTEMPTS:
        _challenges.pop(challenge_id, None)
        return None
    _challenges[challenge_id] = (user_id, expires, attempts + 1)
    return user_id


def clear_challenge(challenge_id: str) -> None:
    _challenges.pop(challenge_id, None)


# ── Status ─────────────────────────────────────────────────────────────


@user_router.get("/status")
def totp_status(current: CurrentUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "enabled": bool(user.totp_secret_enc and user.totp_enabled_at),
        "enabled_at": user.totp_enabled_at.isoformat() if user.totp_enabled_at else None,
    }


# ── Setup (two-step to guarantee the user scanned the QR) ──────────────


@user_router.post("/setup-init")
def setup_init(current: CurrentUser = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Return a fresh secret + QR. Nothing is persisted here — the
    client MUST call /setup with a verified code + the same secret to
    activate. Idempotent: existing 2FA users can regenerate (their
    current secret keeps working until they confirm the new one)."""
    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    secret = totp_service.generate_secret()
    uri = totp_service.provisioning_uri(secret, account_name=user.email)
    qr = totp_service.qr_png_base64(uri)
    return {"secret": secret, "otpauth_url": uri, "qr_data_url": qr}


@user_router.post("/setup", response_model=dict)
def setup(body: TOTPSetupIn, request: Request,
          current: CurrentUser = Depends(get_current_user),
          db: Session = Depends(get_db)):
    if not totp_service.verify_code(body.secret, body.code):
        raise HTTPException(status_code=400, detail={
            "message": "Invalid TOTP code — did you enter the current 6-digit code from your authenticator?",
        })
    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    recovery_codes = totp_service.generate_recovery_codes()
    hashed = totp_service.hash_recovery_codes(recovery_codes)

    user.totp_secret_enc = totp_service.encrypt_secret(body.secret)
    user.totp_recovery_codes = hashed
    user.totp_enabled_at = datetime.now(timezone.utc)

    audit_service.record(
        db, current, "TOTP_ENABLED",
        target_type="user", target_id=str(user.id),
        metadata={"recovery_codes_issued": len(recovery_codes)},
        request=request,
    )
    db.commit()
    return {"enabled": True, "recovery_codes": recovery_codes,
            "message": "2FA enabled — save your recovery codes NOW. They will not be shown again."}


# ── Self-disable ───────────────────────────────────────────────────────


@user_router.post("/disable")
def disable(body: TOTPDisableIn, request: Request,
            current: CurrentUser = Depends(get_current_user),
            db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current.id).first()
    if not user or not user.totp_secret_enc:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Password incorrect")
    secret = totp_service.decrypt_secret(user.totp_secret_enc)
    # Accept either a TOTP code OR a recovery code
    ok = totp_service.verify_code(secret, body.code)
    if not ok:
        idx = totp_service.verify_recovery_code(body.code, user.totp_recovery_codes or [])
        ok = idx is not None
    if not ok:
        raise HTTPException(status_code=401, detail="TOTP code invalid")
    user.totp_secret_enc = None
    user.totp_enabled_at = None
    user.totp_recovery_codes = []
    audit_service.record(
        db, current, "TOTP_DISABLED",
        target_type="user", target_id=str(user.id),
        metadata={"self": True}, request=request,
    )
    db.commit()
    return {"enabled": False}


# ── Login challenge exchange ───────────────────────────────────────────


@user_router.post("/challenge", response_model=LoginResponse)
def challenge(body: TOTPChallengeIn, request: Request, response: Response,
              db: Session = Depends(get_db)):
    """Public — accepts {challenge_id, code} and returns the standard
    LoginResponse if the code is valid."""
    user_id = _consume_challenge(body.challenge_id)
    if user_id is None:
        raise HTTPException(status_code=401, detail={
            "message": "Challenge expired or too many attempts. Please sign in again.",
        })
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.totp_secret_enc:
        clear_challenge(body.challenge_id)
        raise HTTPException(status_code=401, detail="2FA no longer valid")
    secret = totp_service.decrypt_secret(user.totp_secret_enc)

    ok = totp_service.verify_code(secret, body.code)
    used_recovery: Optional[int] = None
    if not ok:
        used_recovery = totp_service.verify_recovery_code(
            body.code, user.totp_recovery_codes or [])
        ok = used_recovery is not None
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    # Success — clear the challenge, invalidate the used recovery code,
    # issue tokens.
    clear_challenge(body.challenge_id)
    if used_recovery is not None:
        codes = list(user.totp_recovery_codes or [])
        codes[used_recovery] = None  # single-use
        user.totp_recovery_codes = [c for c in codes if c is not None]

    audit_service.record(
        db, user, "TOTP_LOGIN_SUCCESS",
        target_type="user", target_id=str(user.id),
        metadata={"used_recovery_code": used_recovery is not None},
        request=request,
    )
    db.commit()

    access, refresh = AuthService(db).issue_tokens(user)
    # Import lazily to avoid a circular import at module load.
    from routers.auth import _login_response
    return _login_response(response, user, access, refresh, request=request)


# ── Admin force-disable ────────────────────────────────────────────────


@admin_router.post("/{user_id}/2fa/disable")
def admin_disable(user_id: int, request: Request,
                  current: CurrentUser = Depends(requires_roles("SUPER_ADMIN")),
                  db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id,
                                 User.organization_id == current.organization_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.totp_secret_enc:
        return {"enabled": False, "message": "Already disabled"}
    user.totp_secret_enc = None
    user.totp_enabled_at = None
    user.totp_recovery_codes = []
    audit_service.record(
        db, current, "TOTP_DISABLED",
        target_type="user", target_id=str(user.id),
        metadata={"self": False, "actor_id": current.id}, request=request,
    )
    db.commit()
    return {"enabled": False, "target_user_id": user.id}


# The register_all() shim expects a `router` symbol — we export TWO,
# grouped as a tuple for that consumer.
def register(app):
    app.include_router(user_router)
    app.include_router(admin_router)
