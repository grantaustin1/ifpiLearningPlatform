"""Observability + security middleware (Iter 30d).

Adds five tiny middlewares that mirror ERP360's Sprint C hardening:

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

4. **API rate-limit headers** — every `/api/*` response carries
   `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `Retry-After`
   (on 429). A generous per-IP cap (300/min) avoids hurting real users
   while giving bots a clear signal.

5. **Auto audit-log** — mutating requests under `/api/*` are recorded
   in the `audit_logs` table as a compliance safety net, even when
   handlers forget to call `audit_service.record()` explicitly.

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


# Iter 38 — request-summary logger + n+1 threshold. Threshold is
# generous (real n+1s bloat to hundreds of queries — 25 is a signal,
# not a hard cap). Adjust via env `N_PLUS_ONE_THRESHOLD`.
import os as _os_iter38
_req_logger = logging.getLogger("ifpi.request")
_N_PLUS_ONE_THRESHOLD = int(_os_iter38.environ.get("N_PLUS_ONE_THRESHOLD", "25"))


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
        # Iter 38 — Reset the per-request query counter at request start.
        # Reads at request end feed the [req] log line + optional
        # X-Query-Count response header for n+1 hunting.
        try:
            from core.query_counter import reset_query_count
            reset_query_count()
        except Exception:  # noqa: BLE001
            pass
        # Iter 32b — Propagate correlation ID into Sentry's per-request
        # scope. sentry-sdk 2.x isolates scopes per FastAPI request via
        # FastApiIntegration, so `set_tag()` here attaches to any
        # exception/breadcrumb captured during THIS request only.
        # No-op when SENTRY_DSN is unset (client is Noop).
        try:
            import sentry_sdk
            if sentry_sdk.get_client().dsn:
                sentry_sdk.set_tag("correlation_id", cid)
                sentry_sdk.set_context("request", {
                    "correlation_id": cid,
                    "path": request.url.path,
                    "method": request.method,
                })
        except Exception:  # noqa: BLE001 - never let observability break the request
            pass
        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[self.HEADER] = cid
            # Iter 38 — dev/staging aid for n+1 hunting; production
            # ships with EXPOSE_QUERY_COUNT_HEADER unset (default).
            import os
            if os.environ.get("EXPOSE_QUERY_COUNT_HEADER") == "true":
                try:
                    from core.query_counter import get_query_count
                    response.headers["X-Query-Count"] = str(get_query_count())
                except Exception:  # noqa: BLE001
                    pass
            # Iter 38 — structured request summary line. One line per
            # request, greppable via `[req]` prefix, exportable to
            # Grafana/Loki/Datadog without further transformation.
            try:
                from core.query_counter import get_query_count
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                qcount = get_query_count()
                path = request.url.path
                # Skip noise: static assets, health probes, docs UI
                if not (path.startswith("/static") or path in ("/health", "/docs", "/openapi.json", "/redoc")):
                    _req_logger.info(
                        "[req] method=%s path=%s status=%d duration_ms=%d queries=%d cid=%s",
                        request.method, path, response.status_code,
                        elapsed_ms, qcount, cid,
                    )
                    # Flag likely n+1 offenders in real time.
                    if qcount >= _N_PLUS_ONE_THRESHOLD:
                        _req_logger.warning(
                            "[n+1?] path=%s method=%s queries=%d duration_ms=%d cid=%s "
                            "— audit selectinload/joinedload",
                            path, request.method, qcount, elapsed_ms, cid,
                        )
            except Exception:  # noqa: BLE001
                pass
            return response
        finally:
            # Iter 38 — release the query counter slot for this request
            try:
                from core.query_counter import drop_query_count
                drop_query_count()
            except Exception:  # noqa: BLE001
                pass
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
        # Iter 26 — Test-only IP pinning header. Prevents CI flakiness
        # from parallel workers sharing the K8s ingress upstream IP.
        # Gated behind `ALLOW_TEST_TOKEN_HEADER=true`; never active in
        # production because the env var is off there.
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
# 4. CSRF double-submit cookie (Iter 30h)
# ─────────────────────────────────────────────────────────────────────


class CSRFProtectMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF guard.

    Enforcement rules:
    - Only when `CSRF_ENABLED=true` in config (opt-in for safe rollout).
    - Only on mutating methods: POST/PUT/PATCH/DELETE.
    - Only when the request presents the auth cookie (`ifpi_auth_token`).
      Bearer-header requests (API tokens, mobile clients, tests) bypass
      the check — they aren't vulnerable to CSRF since a browser can't
      attach an arbitrary Authorization header cross-origin.
    - Certain public/entry-point paths bypass (login, register, refresh,
      SSO exchange, public catalog, portal, lead capture, xAPI receiver,
      SCORM runtime, invitation accept). Login/refresh have their own
      Origin-check via SameSite=lax; enforcing CSRF on them would create
      a chicken-and-egg problem where the client has no CSRF token yet.

    On success: pass through. On failure: return 403 CSRF_TOKEN_MISMATCH
    in the standard envelope.
    """

    UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
    # Paths that are always exempt. Prefix match — everything under these
    # trees also bypasses.
    EXEMPT_PREFIXES = (
        "/api/auth/login",
        "/api/member/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/auth/sso-exchange",
        "/api/auth/sso-status",
        "/api/auth/2fa/challenge",   # 2FA login exchange (no session yet)
        "/api/leads",           # public lead capture + embed.js
        "/api/public/",
        "/api/portal/",
        "/api/scorm/",
        "/api/xapi/",
        "/api/invitations/",    # accept-invite is a public POST
        "/api/branding/public",
        "/api/uploads/files/",
    )
    COOKIE_NAME = "ifpi_auth_token"
    CSRF_COOKIE = "ifpi_csrf"
    HEADER_NAME = "x-csrf-token"

    async def dispatch(self, request: Request, call_next):
        from core.config import settings as _s
        if not _s.csrf_enabled:
            return await call_next(request)
        if request.method.upper() not in self.UNSAFE_METHODS:
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)
        # Bearer-header auth is exempt (API tokens, tests) — a browser
        # can't set an arbitrary Authorization header cross-origin, so
        # CSRF isn't the applicable threat model.
        authz = request.headers.get("authorization", "")
        if authz.lower().startswith("bearer "):
            return await call_next(request)
        # From here on: caller is (or claims to be) a cookie-authed
        # browser session — enforce double-submit.
        auth_cookie = request.cookies.get(self.COOKIE_NAME)
        if not auth_cookie:
            # No cookie session at all → let the auth dependency handle
            # the 401. Not a CSRF failure.
            return await call_next(request)
        cookie_token = request.cookies.get(self.CSRF_COOKIE)
        header_token = request.headers.get(self.HEADER_NAME)
        if (not cookie_token or not header_token
                or not _consteq(cookie_token, header_token)):
            return _err(403, "CSRF_TOKEN_MISMATCH",
                        "CSRF token missing or invalid — refresh the page "
                        "and retry.")
        return await call_next(request)


# ─────────────────────────────────────────────────────────────────────
# 5. API rate-limit headers (design recommendation #15)
# ─────────────────────────────────────────────────────────────────────

class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard rate-limit headers to every `/api/*` response.

    Uses a generous per-IP cap (300 req / 60 s) so legitimate users
    never hit it.  When the cap is exceeded we return 429 with
    `Retry-After` and the usual error envelope.

    Headers injected on every response:
      X-RateLimit-Limit     — total requests allowed per window
      X-RateLimit-Remaining — requests left in current window
      X-RateLimit-Reset     — unix timestamp when the window resets
    """

    LIMIT = 300
    WINDOW_SECS = 60.0
    # Paths that skip rate-limiting (health probes, docs, static)
    EXEMPT_PREFIXES = (
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/static",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from services.rate_limits import SlidingWindowLimiter
        self._limiter = SlidingWindowLimiter(
            limit=self.LIMIT, window_seconds=self.WINDOW_SECS,
        )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        ip = self._client_ip(request)
        allowed, remaining = self._limiter.check(ip)
        reset_ts = int(time.time() + self.WINDOW_SECS)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests — try again shortly.",
                        "status": 429,
                        "correlation_id": get_correlation_id(),
                    }
                },
                headers={
                    "Retry-After": str(int(self.WINDOW_SECS)),
                    "X-RateLimit-Limit": str(self.LIMIT),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_ts),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.LIMIT)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_ts)
        return response

    @staticmethod
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


# ─────────────────────────────────────────────────────────────────────
# Iter 32 · Security headers
# ─────────────────────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defense-in-depth response headers on every request.

    Rationale (per OWASP secure-headers project):
      - `Strict-Transport-Security` — pins browsers to HTTPS for 1 year
        after first visit. Prevents ssl-strip MITM downgrades.
      - `X-Content-Type-Options: nosniff` — kills MIME sniffing which
        can turn a text/plain upload into executable JS.
      - `X-Frame-Options: DENY` — blocks the app from being iframed,
        defeats clickjacking.
      - `Referrer-Policy: strict-origin-when-cross-origin` — leaks the
        path portion of the URL only to same-origin navigations.
      - `Permissions-Policy` — disables geolocation, camera, mic APIs
        by default (we don't use them; opt-in individual endpoints if
        we ever need to).
      - `Content-Security-Policy` — restricts what the browser will
        execute. Report-Only in non-prod so devs still get warnings
        without breakage. Enforced in prod.

    HSTS is intentionally NOT set when serving over HTTP (dev/preview
    without HTTPS) — that would prevent the browser from ever
    reaching the site via HTTP again, breaking local dev.
    """

    # A permissive-but-safer-than-nothing CSP. Frontend inlines some
    # styles and uses Google Fonts + our own CDN. Adjust once we've
    # scoped every legitimate origin.
    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # CRA/React inline runtime chunks
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' data: blob: https:; "
        "connect-src 'self' https: wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    )
    PERMISSIONS_POLICY = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
        "magnetometer=(), gyroscope=(), accelerometer=()"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # OpenAPI/Swagger docs need looser inline-script rules — skip
        # CSP there or the docs page white-screens.
        is_docs = request.url.path.startswith(("/api/docs", "/api/redoc",
                                                "/api/openapi.json"))
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", self.PERMISSIONS_POLICY)
        # Only set HSTS when we know the request came in over HTTPS
        # (either directly or via an X-Forwarded-Proto=https from the
        # ingress). Setting HSTS on plain HTTP would brick localhost.
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        is_https = request.url.scheme == "https" or forwarded_proto == "https"
        if is_https:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if not is_docs:
            # In non-prod deployments we emit Report-Only so devs see
            # violations in the console without breaking pages.
            from core.config import settings as _s
            csp_header = ("Content-Security-Policy" if _s.environment == "production"
                          else "Content-Security-Policy-Report-Only")
            headers.setdefault(csp_header, self.CSP)
        return response


def _consteq(a: str, b: str) -> bool:
    """Constant-time string compare — resists timing oracle attacks."""
    import hmac
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ─────────────────────────────────────────────────────────────────────
# Public installer — one line in server.py
# ─────────────────────────────────────────────────────────────────────


def install_middleware(app: FastAPI) -> None:
    """Wire up correlation-ID, exception envelope, brute-force lockout, CSRF,
    rate-limit headers, security headers, and auto audit-log.

    Order matters (middleware runs in REVERSE order of registration):
      1. CorrelationId FIRST registered → LAST executed on outbound path
         (so response headers include the ID).
      2. BruteForce → runs early on inbound; blocks bad-actor logins.
      3. CSRF → runs after brute-force so brute-force gate isn't itself
         CSRF-gated (login is exempt anyway).
      4. SecurityHeaders → adds headers on the way out.
      5. RateLimitHeaders → counts requests and adds rate-limit headers.
      6. AuditLog → records mutating requests after the handler runs.
    """
    from core.audit_middleware import AuditLogMiddleware
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(LoginBruteForceMiddleware)
    app.add_middleware(CSRFProtectMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitHeadersMiddleware)
    app.add_middleware(AuditLogMiddleware)
    install_exception_handlers(app)
