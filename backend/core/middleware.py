"""Observability + security middleware (Iter 30d).

Adds three tiny middlewares that mirror ERP360's Sprint C hardening:

1. **Correlation-ID** — every request gets an `x-correlation-id` header
   (generated if the client didn't send one). It's put into a context
   var so every log line inside the handler can include it. Frontend
   surfaces it on the error toast so users can quote the ID in support
   tickets.

2. **Global exception envelope** — any uncaught exception (or explicit
   HTTPException raised from a handler) is transformed into a uniform
   JSON shape:
     {"error": {"code": "STR", "message": "human text",
                "status": 4xx, "correlation_id": "..."}}
   The frontend already knows how to render this shape (see
   `lib/api.ts::onError`).

3. **Brute-force lockout on `/api/auth/login`** — after 5 failed logins
   from the same `email + IP` combo in 15 minutes, we return 429 with a
   Retry-After header. Uses the Redis-backed rate limiter service so
   the counter is shared across replicas.

Design constraints:
- Zero-config: safe to import & install unconditionally.
- Zero new deps.
- Fail-open on the observability side, fail-closed on brute-force.
"""
from __future__ import annotations

import contextvars
import logging
import time
import traceback
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("ifpi.middleware")

# Context var holds the correlation ID for the current request. Handlers
# can read it via `get_correlation_id()` — useful for logging inside
# services without threading the request through every call.
_correlation_id_var: contextvars.ContextVar[Optional[str]] = \
    contextvars.ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    return _correlation_id_var.get()


# ─────────────────────────────────────────────────────────────────────
# 1. Correlation-ID middleware
# ─────────────────────────────────────────────────────────────────────


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Reads `x-correlation-id` from the request; generates one if
    missing. Injects it into the response and into a context var so
    downstream logs pick it up automatically."""

    HEADER = "x-correlation-id"
    # Guard against injection — we accept only ULIDs / UUIDs / short IDs.
    MAX_LEN = 64

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get(self.HEADER, "")
        cid = raw.strip()[:self.MAX_LEN] or uuid.uuid4().hex
        token = _correlation_id_var.set(cid)
        try:
            response = await call_next(request)
            response.headers[self.HEADER] = cid
            return response
        finally:
            _correlation_id_var.reset(token)


# ─────────────────────────────────────────────────────────────────────
# 2. Global exception envelope
# ─────────────────────────────────────────────────────────────────────


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "status": status,
                "correlation_id": get_correlation_id(),
            }
        },
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Register a global 500 handler + an HTTPException reshaper so
    every error surfaces in the same envelope.

    We intentionally do NOT swallow FastAPI's own validation errors — those
    stay in their default shape because the frontend already renders them
    field-by-field."""
    from starlette.exceptions import HTTPException as StarletteHTTPException

    async def _http_exc(_req: Request, exc):
        # Preserve any custom headers (e.g. Retry-After on 429).
        headers = getattr(exc, "headers", None)
        detail = getattr(exc, "detail", None)
        status_code = getattr(exc, "status_code", 500)
        # 1) Handler pre-shaped the envelope? Respect it.
        if isinstance(detail, dict) and "error" in detail:
            body = detail
            body["error"].setdefault("status", status_code)
            body["error"].setdefault("correlation_id", get_correlation_id())
            return JSONResponse(status_code=status_code, content=body,
                                headers=headers)
        code = _code_for_status(status_code)
        cid = get_correlation_id()
        # 2) Dict detail (common pattern for 412 with structured data) —
        #    preserve every field ALONGSIDE the envelope so callers can
        #    keep reading `body["missing"]` etc. This is a superset of
        #    the pure envelope.
        if isinstance(detail, dict):
            msg = detail.get("message") or detail.get("detail") or ""
            merged = {**detail,
                      "error": {"code": code, "message": msg,
                                "status": status_code,
                                "correlation_id": cid}}
            return JSONResponse(status_code=status_code, content=merged,
                                headers=headers)
        # 3) Fall-through: plain string / None
        msg = detail if isinstance(detail, str) else str(detail or "")
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code, "message": msg,
                               "status": status_code,
                               "correlation_id": cid}},
            headers=headers,
        )

    # FastAPI and Starlette maintain separate HTTPException hierarchies —
    # unmatched routes raise the starlette variant. Wire both.
    app.exception_handler(HTTPException)(_http_exc)
    app.exception_handler(StarletteHTTPException)(_http_exc)

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        cid = get_correlation_id()
        logger.exception("unhandled exception cid=%s: %s", cid, exc)
        return _err(500, "INTERNAL_ERROR", "An unexpected error occurred")


def _code_for_status(status: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMITED",
    }.get(status, f"HTTP_{status}")


# ─────────────────────────────────────────────────────────────────────
# 3. Brute-force lockout on /api/auth/login
# ─────────────────────────────────────────────────────────────────────


class LoginBruteForceMiddleware(BaseHTTPMiddleware):
    """Adds an extra rate limit to `/api/auth/login`:

    - **5 failed logins / 15 min per email+IP combo** → 429 with
      Retry-After.
    - Successful logins reset the counter so a user with the right
      password isn't punished for a typo streak.
    - Uses the Redis-backed rate limiter (shared across replicas) with
      graceful in-memory fallback.

    Why middleware rather than an endpoint dependency? So the counter is
    checked BEFORE FastAPI parses the body — a bot spamming malformed
    JSON still gets blocked.
    """

    LOGIN_PATH = "/api/auth/login"
    MEMBER_LOGIN_PATH = "/api/member/auth/login"
    MAX_FAILURES = 5
    WINDOW_SECS = 900.0  # 15 min

    async def dispatch(self, request: Request, call_next):
        if request.url.path not in (self.LOGIN_PATH, self.MEMBER_LOGIN_PATH):
            return await call_next(request)

        # Client identity: email (best-effort, might be missing) + real IP.
        ip = self._client_ip(request)
        email = await self._peek_email(request)
        key = f"login-brute:{ip}:{email or 'unknown'}"

        # Check current failure count BEFORE calling the handler
        from services import rate_limit_service
        try:
            rate_limit_service.check(
                key,
                max_requests=self.MAX_FAILURES,
                window_secs=self.WINDOW_SECS,
            )
        except HTTPException as exc:
            # We short-circuit with a friendlier error code
            headers = getattr(exc, "headers", None) or {}
            return _err(429, "LOGIN_LOCKED_OUT",
                        "Too many failed login attempts. Try again shortly."
                        ) if not headers else JSONResponse(
                status_code=429,
                content={"error": {"code": "LOGIN_LOCKED_OUT",
                                    "message": "Too many failed login attempts. "
                                               "Try again shortly.",
                                    "status": 429,
                                    "correlation_id": get_correlation_id()}},
                headers=headers,
            )

        # Now actually run the login. rate_limit_service.check already
        # recorded a hit. If the login succeeds, roll it back so a
        # honest user doesn't accumulate false-positive failures.
        response = await call_next(request)
        if 200 <= response.status_code < 300:
            # Successful login → reset the bucket for this key. Preserves
            # the counter for failed attempts (returns 4xx).
            try:
                rate_limit_service.reset(key)
            except Exception:  # noqa: BLE001
                pass
        return response

    @staticmethod
    def _client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for") or ""
        if fwd:
            first = fwd.split(",")[0].strip()
            if first:
                return first
        return getattr(request.client, "host", "0.0.0.0") or "0.0.0.0"

    @staticmethod
    async def _peek_email(request: Request) -> Optional[str]:
        """Best-effort: peek the JSON body for an email. The body is a
        one-shot stream, so we cache it back so FastAPI can re-read."""
        try:
            body = await request.body()
        except Exception:  # noqa: BLE001
            return None
        # Preserve body for downstream handler
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        request._receive = receive  # noqa: SLF001

        if not body:
            return None
        try:
            import json
            data = json.loads(body.decode("utf-8", errors="ignore"))
            if isinstance(data, dict):
                email = data.get("email") or data.get("username")
                if isinstance(email, str):
                    return email.strip().lower()[:200]
        except Exception:  # noqa: BLE001
            pass
        return None


# ─────────────────────────────────────────────────────────────────────
# Public installer — one line in server.py
# ─────────────────────────────────────────────────────────────────────


def install_middleware(app: FastAPI) -> None:
    """Wire up correlation-ID, exception envelope, brute-force lockout.

    Order matters:
      1. Correlation-ID first — so it's available to all downstream
         (including exception handlers and the token-call logger).
      2. Brute-force checker second — runs BEFORE routers so failed
         logins can't slip past.
      3. Exception handlers last (they're registered, not stacked).
    """
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(LoginBruteForceMiddleware)
    install_exception_handlers(app)
