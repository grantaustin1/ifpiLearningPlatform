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
# Iter 22 — Cookie + CSRF auth helpers for tests.
#
# In strict cookie mode (`AUTH_COOKIE_MODE=on`), login responses do not
# expose `access_token` UNLESS the server-side test bypass env var
# `ALLOW_TEST_TOKEN_HEADER=true` is set (dev/test only — never in prod).
#
# Two auth paths for test code:
# (1) NEW tests should call `authed_session()` — returns a pure cookie
#     Session; auth flows through the `ifpi_auth_token` HttpOnly cookie
#     and the CSRF header is auto-mirrored on every unsafe request via
#     the `Session.request` monkey-patch below. This is the recommended
#     path going forward and mirrors the real browser client.
#
# (2) LEGACY tests still use the `X-Return-Token: true` header + Bearer
#     token pattern. They rely on the module-level monkey-patch which
#     sets that header globally. This is preserved unchanged so ~40
#     existing test files don't need to be rewritten. Migration to (1)
#     is on the backlog.
# ─────────────────────────────────────────────────────────────────


<<<<<<< HEAD
def authed_session(email: str, password: str, base_url: str = ""):
=======
def authed_session(email: str, password: str, base_url: str = "") -> "requests.Session":
>>>>>>> origin/main
    """Log in and return a cookie-authenticated `requests.Session`.

    Uses ONLY the HttpOnly session cookie + CSRF cookie/header pair —
    no `X-Return-Token` bypass, no Bearer fallback. This mirrors how a
    real browser client authenticates in production."""
    import requests

    url = base_url or os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    s = requests.Session()
    # Explicitly disable the legacy header on this session so it stays pure.
    s._skip_x_return_token = True  # type: ignore[attr-defined]
    r = s.post(f"{url}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("Account has 2FA enabled — clear it first")
    # CSRF header is auto-mirrored by the monkey-patch below on every
    # unsafe request; we leave the session bare so cookies alone drive auth.
    return s


import requests as _rq_module  # noqa: E402

_orig_request = _rq_module.api.request
_orig_session_request = _rq_module.Session.request
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _patched_request(method: str, url: str, **kwargs):  # pragma: no cover
    """Module-level `requests.get/post/...` calls: legacy tests bypass
    cookie-only mode via `X-Return-Token: true` (server-side gated behind
    the `ALLOW_TEST_TOKEN_HEADER` env var — never enabled in production)."""
    if "headers" not in kwargs or kwargs["headers"] is None:
        kwargs["headers"] = {}
    kwargs["headers"].setdefault("X-Return-Token", "true")
    return _orig_request(method, url, **kwargs)


def _patched_session_request(self, method, url, **kwargs):  # pragma: no cover
    """Session-level requests:
    - Legacy sessions (default): auto-add `X-Return-Token: true` header.
    - Pure-cookie sessions (via `authed_session()` — flagged with
      `_skip_x_return_token=True`): auto-mirror the `ifpi_csrf` cookie
      into the `X-CSRF-Token` header on unsafe methods."""
    if getattr(self, "_skip_x_return_token", False):
        # Pure-cookie path — mirror CSRF header from cookie on unsafe methods
        if method.upper() in _UNSAFE_METHODS and not getattr(self, "_skip_csrf_autoinject", False):
            headers = kwargs.get("headers") or {}
            already_bearer = any(
                k.lower() == "authorization"
                for k in list(headers.keys()) + list(self.headers.keys())
            )
            already_csrf = any(k.lower() == "x-csrf-token" for k in headers)
            if not already_bearer and not already_csrf:
                csrf = self.cookies.get("ifpi_csrf")
                if csrf:
                    headers = dict(headers)
                    headers["X-CSRF-Token"] = csrf
                    kwargs["headers"] = headers
    else:
        # Legacy path — inject X-Return-Token if not already set
        if "X-Return-Token" not in self.headers:
            self.headers["X-Return-Token"] = "true"
    return _orig_session_request(self, method, url, **kwargs)


_rq_module.api.request = _patched_request
_rq_module.request = _patched_request
_rq_module.Session.request = _patched_session_request
