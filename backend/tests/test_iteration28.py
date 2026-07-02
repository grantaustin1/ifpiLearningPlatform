"""Iter 27b + 27c + P2 (token analytics + SCORM shim) + P3 (public catalog).

Runs against the live REACT_APP_BACKEND_URL preview backend.
"""
from __future__ import annotations

import os
from typing import Optional

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
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _login("learner@ifpi.org", "learner123")


def _mint_token(admin: requests.Session, name: str, scopes: list[str]) -> str:
    r = admin.post(f"{BASE_URL}/api/admin/api-tokens",
                   json={"name": name, "scopes": scopes,
                         "expires_in_days": 1}, timeout=10)
    assert r.status_code == 201, r.text
    return r.json()["token"]


# ─── Iter 27b — mind map ────────────────────────────────────────────
def test_mindmap_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/mindmap/1", timeout=10)
    assert r.status_code == 403


def test_mindmap_missing_course_404(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/mindmap/999999", timeout=15)
    assert r.status_code == 404


def test_mindmap_generate_shape(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/mindmap/1?max_topics=3", timeout=60)
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root"]["id"] and body["root"]["label"]
    assert isinstance(body["topics"], list)
    assert 1 <= len(body["topics"]) <= 3
    for t in body["topics"]:
        assert t["id"] and t["label"]
        for c in t.get("children") or []:
            assert c["id"] and c["label"]


# ─── Iter 27c — PPTX export ─────────────────────────────────────────
def test_pptx_learner_blocked(learner):
    r = learner.get(f"{BASE_URL}/api/authoring/pptx/1", timeout=15)
    assert r.status_code == 403


def test_pptx_missing_course_404(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/pptx/999999", timeout=15)
    assert r.status_code == 404


def test_pptx_export_returns_pptx_bytes(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/pptx/1", timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert "attachment" in r.headers.get("content-disposition", "")
    # PPTX files are ZIPs — start with "PK"
    assert r.content[:2] == b"PK", r.content[:20]
    assert len(r.content) > 2000


# ─── P2 — API token analytics ──────────────────────────────────────
def test_token_analytics_learner_blocked(learner):
    r = learner.get(f"{BASE_URL}/api/admin/api-tokens/analytics/usage", timeout=10)
    assert r.status_code == 403


def test_token_analytics_returns_series(admin):
    r = admin.get(f"{BASE_URL}/api/admin/api-tokens/analytics/usage?days=7", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7
    assert len(body["series"]) == 7
    for d in body["series"]:
        assert "date" in d and "count" in d and "errors" in d
    assert "by_token" in body
    assert body["total_calls"] >= 0


def test_token_analytics_records_a_call(admin):
    """Fire a request with an API token and confirm it shows in analytics."""
    tok = _mint_token(admin, "analytics test", ["ADMIN"])
    # Fire a request with this token
    r = requests.get(f"{BASE_URL}/api/organization",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    assert r.status_code == 200

    # Check the analytics — total_calls should be > 0
    a = admin.get(f"{BASE_URL}/api/admin/api-tokens/analytics/usage?days=1", timeout=10)
    assert a.json()["total_calls"] >= 1


# ─── P2 — SCORM runtime shim ────────────────────────────────────────
def test_scorm_runtime_js_served():
    r = requests.get(f"{BASE_URL}/api/scorm/runtime.js", timeout=10)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    body = r.text
    # Sanity — the essential SCORM APIs must be defined
    assert "window.API" in body
    assert "window.API_1484_11" in body
    assert "LMSInitialize" in body
    assert "LMSSetValue" in body
    assert "cmi.core.lesson_status" in body
    # Must not have hardcoded LMS URL — should compute from currentScript
    assert "LMS_ORIGIN" in body


# ─── P3 — public catalog + cert verify ──────────────────────────────
def test_cert_verify_anon_404_on_junk():
    r = requests.get(f"{BASE_URL}/api/public/certificates/verify/JUNKCODE123", timeout=10)
    assert r.status_code == 404


def test_cert_verify_anon_returns_pii_safe_shape():
    """We can't guarantee a specific cert exists, but we can verify the
    endpoint doesn't leak PII on 404 (no user email leaked)."""
    r = requests.get(f"{BASE_URL}/api/public/certificates/verify/x", timeout=10)
    # 400 (too short) or 404 both acceptable
    assert r.status_code in (400, 404)
    body = r.json()
    # No email fields should ever appear in the error response
    assert "@" not in str(body)


def test_catalog_requires_authorization():
    r = requests.get(f"{BASE_URL}/api/public/catalog", timeout=10)
    assert r.status_code == 401


def test_catalog_authd_admin(admin):
    r = admin.get(f"{BASE_URL}/api/public/catalog", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 0
    for c in body["items"][:3]:
        assert c["id"] and c["title"]
        # No PII / no learner-scoped data
        assert "email" not in c and "user_id" not in c


def test_catalog_api_token_needs_read_catalog_scope(admin):
    """Token without read:catalog is rejected. Token WITH it works."""
    # Without scope
    tok_no = _mint_token(admin, "no-scope test", ["LEARNER"])
    r = requests.get(f"{BASE_URL}/api/public/catalog",
                     headers={"Authorization": f"Bearer {tok_no}"}, timeout=10)
    assert r.status_code == 403

    # With scope
    tok_ok = _mint_token(admin, "catalog test", ["read:catalog"])
    r2 = requests.get(f"{BASE_URL}/api/public/catalog",
                      headers={"Authorization": f"Bearer {tok_ok}"}, timeout=10)
    assert r2.status_code == 200
    assert r2.json()["count"] >= 0


def test_catalog_search_filters_results(admin):
    r = admin.get(f"{BASE_URL}/api/public/catalog?q=IFPI", timeout=10)
    assert r.status_code == 200
    # Every returned item's title or description must contain "IFPI"
    for c in r.json()["items"]:
        blob = f"{c['title'] or ''} {c.get('description') or ''}".lower()
        assert "ifpi" in blob, c
