"""HTTP-only cookie transport for the IFPI session token.

Mirrors ERP360's `auth/cookies.py`. Three modes via `AUTH_COOKIE_MODE`:

- ``off``  — header-only auth (legacy)
- ``dual`` — cookie set AND token in JSON body (default; safe migration)
- ``on``   — cookie only, body omits token (post-cutover)

Iter 30h adds the CSRF double-submit cookie:

- ``ifpi_csrf`` — NON-HttpOnly (so JS can read it and stamp
  `X-CSRF-Token` on mutating requests). Issued on every login/refresh.
"""
from __future__ import annotations

import secrets

from fastapi import Response

from core.config import settings

COOKIE_NAME = "ifpi_auth_token"
REFRESH_COOKIE = "ifpi_refresh_token"
CSRF_COOKIE = "ifpi_csrf"
COOKIE_PATH = "/api"


def _cookie_attrs() -> dict:
    samesite = (settings.auth_cookie_samesite or "lax").lower()
    secure = settings.auth_cookie_secure
    if samesite == "none":
        secure = True  # browsers require Secure when SameSite=None
    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": COOKIE_PATH,
    }


def _csrf_cookie_attrs() -> dict:
    """CSRF cookie is *readable* by JS (so the frontend can mirror it
    into the X-CSRF-Token header). Must be scoped to ``/`` (not ``/api``)
    so pages served from any path can read it via ``document.cookie``.
    Otherwise inherits the same SameSite/Secure attributes as the auth
    cookie."""
    attrs = _cookie_attrs()
    attrs["httponly"] = False
    attrs["path"] = "/"
    return attrs


def should_include_token_in_body() -> bool:
    return settings.auth_cookie_mode in {"off", "dual"}


def generate_csrf_token() -> str:
    """32 bytes → 43-char url-safe string. Distinct per session."""
    return secrets.token_urlsafe(32)


def set_auth_cookie(response: Response, token: str) -> None:
    if settings.auth_cookie_mode == "off":
        return
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expiration_minutes * 60,
        **_cookie_attrs(),
    )


def set_refresh_cookie(response: Response, token: str) -> None:
    if settings.auth_cookie_mode == "off":
        return
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_days * 86400,
        **_cookie_attrs(),
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    """Issue the double-submit CSRF cookie. Safe to call even when
    csrf_enabled is False — it just seeds the client so the flip to
    enforcement doesn't require a re-login."""
    if settings.auth_cookie_mode == "off":
        return
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=settings.refresh_token_days * 86400,
        **_csrf_cookie_attrs(),
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (COOKIE_NAME, REFRESH_COOKIE):
        response.delete_cookie(name, path=COOKIE_PATH)
    # CSRF cookie is scoped to '/' — must be cleared on the same path.
    response.delete_cookie(CSRF_COOKIE, path="/")
