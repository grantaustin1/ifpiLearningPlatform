"""Iteration 20 retest — Redis rate limiter, public catalog access, regression sanity."""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    import pytest
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests", allow_module_level=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _login("learner@ifpi.org", "learner123")


# ─── Redis Rate Limiter ─────────────────────────────────────────────
def test_public_verify_rate_limiter_triggers_429(learner):
    """Anonymous rapid-fire verifies should trigger 429 with Retry-After."""
    # Fetch a real cert code (fallback: dummy)
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    code = certs[0].get("code") or certs[0].get("cert_code") if certs else "BOGUS-CODE"

    # Reset redis to a clean state
    try:
        import redis
        r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        r.flushdb()
    except Exception:
        pass

    saw_429 = False
    retry_after = None
    for i in range(60):
        resp = requests.get(f"{BASE_URL}/api/public/certificates/verify/{code}", timeout=10)
        if resp.status_code == 429:
            saw_429 = True
            retry_after = resp.headers.get("Retry-After")
            break

    assert saw_429, f"Expected 429 within 60 rapid-fire requests"
    assert retry_after is not None, "Expected Retry-After header on 429"


# ─── Public catalog with API token ──────────────────────────────────
def test_public_catalog_requires_token():
    r = requests.get(f"{BASE_URL}/api/public/catalog", timeout=10)
    assert r.status_code in (401, 403)


def test_public_catalog_with_valid_token(admin):
    # Create an API token via admin console with read:catalog scope
    resp = admin.post(
        f"{BASE_URL}/api/admin/api-tokens",
        json={"name": "TEST_catalog_reader", "scopes": ["read:catalog"]},
        timeout=10,
    )
    if resp.status_code == 404:
        pytest.skip("API-token admin endpoint missing")
    assert resp.status_code in (200, 201), resp.text
    payload = resp.json()
    token = payload.get("token") or payload.get("plain_token") or payload.get("access_token")
    assert token, f"Token not returned: {payload}"
    token_id = payload.get("id")

    try:
        r = requests.get(
            f"{BASE_URL}/api/public/catalog",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Expect catalog list (may be under key or as list)
        if isinstance(body, dict):
            items = body.get("items") or body.get("catalog") or body.get("courses") or []
        else:
            items = body
        assert isinstance(items, list)
    finally:
        if token_id:
            admin.delete(f"{BASE_URL}/api/admin/api-tokens/{token_id}", timeout=10)


# ─── Regression sanity: primary GETs return 200 for both roles ──────
ADMIN_ROUTES = [
    "/api/courses",
    "/api/certificates",
    "/api/admin/users",
    "/api/admin/api-tokens",
    "/api/admin/api-tokens/analytics/spend?days=14",
    "/api/learning-paths",
]

LEARNER_ROUTES = [
    "/api/courses",
    "/api/certificates",
    "/api/learning-paths",
]


@pytest.mark.parametrize("route", ADMIN_ROUTES)
def test_admin_route_ok(admin, route):
    r = admin.get(f"{BASE_URL}{route}", timeout=15)
    assert r.status_code == 200, f"{route} -> {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("route", LEARNER_ROUTES)
def test_learner_route_ok(learner, route):
    r = learner.get(f"{BASE_URL}{route}", timeout=15)
    assert r.status_code == 200, f"{route} -> {r.status_code} {r.text[:200]}"


def test_learner_denied_on_admin_routes(learner):
    r = learner.get(f"{BASE_URL}/api/admin/users", timeout=10)
    assert r.status_code == 403
    r = learner.get(f"{BASE_URL}/api/admin/api-tokens", timeout=10)
    assert r.status_code == 403
