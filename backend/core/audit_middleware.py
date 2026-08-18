"""Automatic audit-log middleware for state-changing API requests.

Records a lightweight AuditLog row for every POST/PUT/PATCH/DELETE
under `/api/*`.  The row contains the HTTP method, path, client IP,
and a snapshot of the Authorization header type (Bearer vs cookie)
so compliance reviewers can see *that* an action happened even if the
application code forgets to call audit_service.record explicitly.

This is a safety-net layer — explicit `audit_service.record()` calls
inside handlers are still preferred because they capture the exact
business action (e.g. "THEME_APPLIED") and the acting user.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("ifpi.audit.middleware")

# Methods that mutate state and therefore get audited.
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Paths we skip: health probes, static assets, docs, auth login/refresh
# (those have their own dedicated logging).
_EXEMPT_PREFIXES = (
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/static",
    "/api/auth/login",
    "/api/auth/refresh",
)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Best-effort audit logging for mutating API requests.

    Uses a short-lived DB session so it never leaks the caller's
    transaction scope. Failures are swallowed — audit must not break
    the request.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only audit mutating methods
        if request.method.upper() not in _MUTATING:
            return response

        path = request.url.path
        if not path.startswith("/api/") or any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return response

        # Fire-and-forget audit record
        try:
            self._record(request, response)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AuditLogMiddleware failed to record: %s", exc)

        return response

    @staticmethod
    def _record(request: Request, response) -> None:
        from core.database import SessionLocal
        from services import audit_service

        ip = _client_ip(request)
        authz = request.headers.get("authorization", "")
        auth_type = "bearer" if authz.lower().startswith("bearer ") else "cookie" if request.cookies.get("ifpi_auth_token") else "none"

        db = SessionLocal()
        try:
            audit_service.record(
                db,
                actor=_SimpleActor(ip=ip),
                action=f"{request.method} {request.url.path}",
                target_type="api_request",
                target_id=None,
                metadata={
                    "method": request.method,
                    "path": str(request.url.path),
                    "query": str(request.url.query),
                    "status_code": response.status_code,
                    "auth_type": auth_type,
                    "ip": ip,
                },
            )
            db.commit()
        finally:
            db.close()


class _SimpleActor:
    """Minimal actor stand-in for middleware-level audit rows."""
    def __init__(self, ip: Optional[str] = None):
        self.id = None
        self.email = f"middleware@{ip or 'unknown'}"
        self.organization_id = None


def _client_ip(request: Request) -> str:
    from core.config import settings as _settings
    if _settings.test_bypass_enabled:
        test_ip = request.headers.get("x-test-client-ip") or ""
        if test_ip.strip():
            return test_ip.strip()
    fwd = request.headers.get("x-forwarded-for") or ""
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return getattr(request.client, "host", "0.0.0.0") or "0.0.0.0"
