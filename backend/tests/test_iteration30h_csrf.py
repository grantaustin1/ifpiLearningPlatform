"""Iter 30h — CSRF double-submit cookie middleware.

Tests run only when REACT_APP_BACKEND_URL is set (skipped in CI without a
live backend). The middleware is opt-in via `CSRF_ENABLED=true`; these
tests toggle the flag by verifying behaviour in whichever mode the live
backend runs in, and also unit-test the middleware directly against a
fresh FastAPI app when the flag is off in the live env.
"""
from __future__ import annotations

import os

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ── Unit tests against a synthetic FastAPI app ─────────────────────────


@pytest.fixture
def csrf_app(monkeypatch):
    """Build a mini FastAPI app with CSRF middleware ENABLED regardless
    of the live backend's config. Uses a bare `/api/things` endpoint."""
    from core import middleware as mw
    from core.config import settings

    monkeypatch.setattr(settings, "csrf_enabled", True)
    app = FastAPI()
    app.add_middleware(mw.CSRFProtectMiddleware)
    mw.install_exception_handlers(app)

    @app.post("/api/things")
    def _create(): return {"ok": True}

    @app.get("/api/things")
    def _list(): return {"items": []}

    @app.post("/api/auth/login")
    def _login(): return {"ok": True}  # exempt path

    return app


def test_csrf_get_requests_pass_through(csrf_app):
    """CSRF applies only to mutating methods."""
    c = TestClient(csrf_app)
    r = c.get("/api/things", cookies={"ifpi_auth_token": "abc"})
    assert r.status_code == 200


def test_csrf_login_path_is_exempt(csrf_app):
    """Login itself has no CSRF token yet — it MUST bypass."""
    c = TestClient(csrf_app)
    r = c.post("/api/auth/login")
    assert r.status_code == 200


def test_csrf_bearer_auth_is_exempt(csrf_app):
    """API tokens / Bearer auth can't be CSRF'd (browsers can't attach
    arbitrary Authorization headers cross-origin)."""
    c = TestClient(csrf_app)
    r = c.post("/api/things",
               headers={"Authorization": "Bearer ifpi_apitoken_xyz"})
    assert r.status_code == 200


def test_csrf_missing_token_returns_403(csrf_app):
    """Cookie-authed POST without X-CSRF-Token header → 403."""
    c = TestClient(csrf_app)
    r = c.post("/api/things",
               cookies={"ifpi_auth_token": "abc", "ifpi_csrf": "expected"})
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "CSRF_TOKEN_MISMATCH"


def test_csrf_mismatched_token_returns_403(csrf_app):
    """Cookie says X, header says Y → 403."""
    c = TestClient(csrf_app)
    r = c.post("/api/things",
               cookies={"ifpi_auth_token": "abc", "ifpi_csrf": "expected"},
               headers={"X-CSRF-Token": "different"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_TOKEN_MISMATCH"


def test_csrf_matching_token_passes(csrf_app):
    """Cookie and header match → request goes through."""
    c = TestClient(csrf_app)
    r = c.post("/api/things",
               cookies={"ifpi_auth_token": "abc", "ifpi_csrf": "same-token"},
               headers={"X-CSRF-Token": "same-token"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_csrf_no_cookie_session_passes(csrf_app):
    """Unauthenticated request: middleware doesn't gate — the auth
    dependency will return 401 down the line. That's not a CSRF concern."""
    c = TestClient(csrf_app)
    r = c.post("/api/things")
    assert r.status_code == 200  # our stub handler; auth would 401 in real app


def test_csrf_disabled_flag_bypasses_middleware(monkeypatch):
    """When csrf_enabled=False the middleware is a no-op regardless."""
    from core import middleware as mw
    from core.config import settings

    monkeypatch.setattr(settings, "csrf_enabled", False)
    app = FastAPI()
    app.add_middleware(mw.CSRFProtectMiddleware)

    @app.post("/api/thing")
    def _create():
        return {"ok": True}

    c = TestClient(app)
    r = c.post("/api/thing", cookies={"ifpi_auth_token": "abc"})
    assert r.status_code == 200


# ── E2E tests against the running backend ─────────────────────────────


@pytest.fixture
def admin_session():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"},
               timeout=10)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


def test_login_sets_csrf_cookie(admin_session):
    """Every login response includes the `ifpi_csrf` cookie."""
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"},
               timeout=10)
    assert r.status_code == 200
    # The CSRF cookie may or may not be visible to `requests` depending
    # on cookie domain rules; use the raw Set-Cookie header instead.
    set_cookie = r.headers.get("set-cookie", "")
    assert "ifpi_csrf=" in set_cookie, (
        f"login response missing ifpi_csrf cookie: {set_cookie!r}"
    )


def test_bearer_flows_unaffected_by_csrf(admin_session):
    """Bearer-header requests bypass CSRF entirely. This is the path all
    existing tests + integrations rely on — MUST NOT regress."""
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    r = admin_session.get(f"{BASE_URL}/api/authoring/status", timeout=10)
    assert r.status_code == 200
