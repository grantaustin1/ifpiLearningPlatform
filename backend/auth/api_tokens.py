"""API token authentication (Iter 21).

Two responsibilities:
 - `mint_token()` — generates a new bearer token, returns plaintext + the
   ApiToken row to persist (only the plaintext is returned to the admin).
 - `authenticate_api_token()` — used by `get_current_user` when the bearer
   string begins with `ifpi_`. Looks up by SHA-256 hash, updates last_used,
   and yields a `CurrentUser` with the token's scopes as roles.

Token format: `ifpi_<8-char-prefix>_<32-char-secret>` (~45 chars total).
The 8-char prefix is stored plain on the row so admins can identify a key
in lists ("ifpi_a1b2c3d4… created 12 May") without leaking the secret.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser
from core.role_registry import normalize_role_names

logger = logging.getLogger("ifpi.api_tokens")

TOKEN_PREFIX = "ifpi_"


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def mint_token() -> tuple[str, str, str]:
    """Returns (plaintext, prefix_for_display, sha256_hash). Caller persists
    prefix + hash on the ApiToken row; plaintext is shown ONCE to the admin
    at creation time and then thrown away."""
    secret = secrets.token_urlsafe(24)
    short = secrets.token_hex(4)            # 8 hex chars — used as the listing prefix
    plaintext = f"{TOKEN_PREFIX}{short}_{secret}"
    return plaintext, short, _hash(plaintext)


def authenticate_api_token(db: Session, plaintext: str) -> Optional[CurrentUser]:
    """Look up a token by hash, verify it's active + unexpired, and return
    a synthetic CurrentUser whose `id` is the token id (negative) and roles
    are the token's scopes. Returns None on any failure."""
    if not plaintext.startswith(TOKEN_PREFIX):
        return None

    from models import ApiToken, Organization

    row = db.query(ApiToken).filter(
        ApiToken.token_hash == _hash(plaintext),
        ApiToken.is_active.is_(True),
    ).first()
    if not row:
        return None
    if row.expires_at:
        if row.expires_at.tzinfo is None:
            # SQLite returns naive datetimes — pretend they're UTC
            expires = row.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires = row.expires_at
        if expires < datetime.now(timezone.utc):
            return None

    # Update last_used (best-effort, doesn't fail auth on commit error)
    try:
        row.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    # Sanity check the org still exists
    org = db.query(Organization).filter(Organization.id == row.organization_id).first()
    if not org:
        return None

    # Roles come out UPPER-cased; but permission scopes like `read:catalog`
    # (contain a colon) are preserved verbatim so scope-aware endpoints can
    # match on them directly.
    raw = list(row.scopes or [])
    scope_tokens = [s for s in raw if isinstance(s, str) and ":" in s]
    role_tokens = normalize_role_names([s for s in raw if isinstance(s, str) and ":" not in s])
    scopes = role_tokens + scope_tokens or ["LEARNER"]

    # Negative id distinguishes synthetic API-token principals from real users.
    return CurrentUser(
        id=-row.id,
        email=f"api-token-{row.id}@{org.slug}.local",
        name=f"API token: {row.name}",
        organization_id=row.organization_id,
        roles=scopes,
    )
