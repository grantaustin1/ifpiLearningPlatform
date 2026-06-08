"""HTTP-only cookie transport for the IFPI session token.

Mirrors ERP360's `auth/cookies.py`. Three modes via `AUTH_COOKIE_MODE`:

- ``off``  — header-only auth (legacy)
- ``dual`` — cookie set AND token in JSON body (default; safe migration)
- ``on``   — cookie only, body omits token (post-cutover)
"""
from __future__ import annotations

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


def should_include_token_in_body() -> bool:
    return settings.auth_cookie_mode in {"off", "dual"}


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


def clear_auth_cookies(response: Response) -> None:
    for name in (COOKIE_NAME, REFRESH_COOKIE):
        response.delete_cookie(name, path=COOKIE_PATH)
