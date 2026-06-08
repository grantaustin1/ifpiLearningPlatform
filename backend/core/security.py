"""Auth primitives: password hashing + JWT encode/decode.

Mirrors ERP360's `core/security.py` shape so the SSO bridge can verify
tokens issued by ERP360 with identical code.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from core.config import settings

logger = logging.getLogger(__name__)

BCRYPT_ROUNDS = 12


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    """True if hash uses fewer rounds than current cost (rehash on next login)."""
    try:
        # bcrypt hash format: $2b$<rounds>$...
        parts = hashed.split("$")
        if len(parts) < 4:
            return True
        return int(parts[2]) < BCRYPT_ROUNDS
    except (ValueError, IndexError):
        return True


def create_access_token(subject: str | int, claims: Optional[dict] = None,
                        expires_minutes: Optional[int] = None) -> str:
    exp_minutes = expires_minutes or settings.jwt_expiration_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
        "type": "access",
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | int, family_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.refresh_token_days)).timestamp()),
        "type": "refresh",
        "fam": family_id,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Raise JWTError on invalid/expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
