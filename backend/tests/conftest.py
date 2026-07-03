"""Test-suite configuration.

All backend tests in this folder are *integration* tests — they hit a
running IFPI backend over HTTP. In CI (GitHub Actions etc.) that backend
is usually not running, so we auto-skip the whole suite unless a live
backend is reachable at REACT_APP_BACKEND_URL.

Local dev: supervisor runs the backend + preview URL is set in
`/app/frontend/.env`. The conftest picks it up and tests run normally.

CI override: set `RUN_INTEGRATION_TESTS=1` to force execution regardless
(useful when a dedicated CI job spins up a backend container first).
"""
from __future__ import annotations

import os
import socket
import urllib.parse

import pytest


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if url:
        return url
    # Fallback: read /app/frontend/.env when running from /app/backend
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    val = line.split("=", 1)[1].strip().rstrip("/")
                    if val:
                        os.environ["REACT_APP_BACKEND_URL"] = val
                        return val
    except FileNotFoundError:
        pass
    return ""


def _reachable(url: str, timeout: float = 2.0) -> bool:
    """Quick TCP probe. HTTP/HTTPS agnostic — we only care that *something*
    listens on the resolved host:port."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


BACKEND_URL = _load_backend_url()
FORCE_RUN = os.environ.get("RUN_INTEGRATION_TESTS") == "1"
_BACKEND_LIVE = bool(BACKEND_URL) and _reachable(BACKEND_URL)


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when the backend is unreachable and the
    operator hasn't explicitly opted in with RUN_INTEGRATION_TESTS=1.

    Static tests (docs completeness, import checks) never touch the
    backend, so they always run — even without a live server."""
    if FORCE_RUN or _BACKEND_LIVE:
        return
    reason = (
        "IFPI backend not reachable at "
        f"{BACKEND_URL or '<unset>'} — integration tests skipped. "
        "Set RUN_INTEGRATION_TESTS=1 to force."
    )
    skip = pytest.mark.skip(reason=reason)
    static_prefixes = ("test_docs_", "test_static_", "test_lint_")
    for item in items:
        module_name = item.nodeid.split("::", 1)[0].split("/")[-1]
        if any(module_name.startswith(p) for p in static_prefixes):
            continue  # static tests always run
        item.add_marker(skip)



# ─────────────────────────────────────────────────────────────────
# Iter 30o — Auth session helper for cookie-only mode.
# When `AUTH_COOKIE_MODE=on`, the login response body no longer carries
# `access_token`. Tests must instead use the session cookie AND stamp
# the `X-CSRF-Token` header on every mutating request. This helper
# handles both transparently.
# ─────────────────────────────────────────────────────────────────


def authed_session(email: str, password: str, base_url: str = "") -> "requests.Session":
    """Log in and return a `requests.Session` that works in ANY
    `AUTH_COOKIE_MODE`. Sets `X-Return-Token: true` so the login
    response body contains the access_token even in cookie-only mode.

    Also attaches the CSRF token header for cookie-authed calls (harmless
    when Bearer is also present)."""
    import requests

    url = base_url or os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    s = requests.Session()
    s.headers["X-Return-Token"] = "true"
    r = s.post(f"{url}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("Account has 2FA enabled — clear it first")
    if body.get("access_token"):
        s.headers["Authorization"] = f"Bearer {body['access_token']}"
    csrf = s.cookies.get("ifpi_csrf")
    if csrf:
        s.headers["X-CSRF-Token"] = csrf
    return s


# ─────────────────────────────────────────────────────────────────
# Iter 30r — Global `X-Return-Token` header for the top-level
# `requests` module. Some tests use `requests.post(...)` directly
# rather than `requests.Session()`; monkey-patch the module-level
# helpers so cookie-only mode doesn't break them either.
# ─────────────────────────────────────────────────────────────────

import requests as _rq_module  # noqa: E402

_orig_request = _rq_module.api.request
_orig_session_request = _rq_module.Session.request


def _patched_request(method: str, url: str, **kwargs):  # pragma: no cover
    if "headers" not in kwargs or kwargs["headers"] is None:
        kwargs["headers"] = {}
    kwargs["headers"].setdefault("X-Return-Token", "true")
    return _orig_request(method, url, **kwargs)


def _patched_session_request(self, method, url, **kwargs):  # pragma: no cover
    # Session-level calls go through here; inject the header if the
    # session hasn't explicitly overridden it.
    if "X-Return-Token" not in self.headers:
        self.headers["X-Return-Token"] = "true"
    return _orig_session_request(self, method, url, **kwargs)


_rq_module.api.request = _patched_request
_rq_module.request = _patched_request
_rq_module.Session.request = _patched_session_request
