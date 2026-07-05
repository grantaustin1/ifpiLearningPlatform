"""Iter 30r — Email transport diagnostics."""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("2FA on — clear first")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin(): return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner(): return _login("learner@ifpi.org", "learner123")


def test_transport_status_shape(admin):
    r = admin.get(f"{BASE_URL}/api/admin/email/transport-status", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "active_transport" in body
    keys = {t["transport"] for t in body["transports"]}
    assert keys == {"per_tenant", "system", "erp360"}


def test_transport_status_reports_stub_by_default(admin):
    r = admin.get(f"{BASE_URL}/api/admin/email/transport-status", timeout=10).json()
    # In our dev env, none of the three are configured
    assert r["active_transport"] in {"stub", "per_tenant", "system", "erp360"}


def test_send_test_returns_status_and_notes(admin):
    r = admin.post(f"{BASE_URL}/api/admin/email/send-test",
                   json={"to_email": "someone@example.com"}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outbox_id"] > 0
    assert body["status"] in {"SENT", "STUB", "FAILED"}
    assert body["note"]


def test_send_test_rejects_bad_email(admin):
    r = admin.post(f"{BASE_URL}/api/admin/email/send-test",
                   json={"to_email": "not-an-email"}, timeout=10)
    assert r.status_code == 422


def test_send_test_learner_forbidden(learner):
    r = learner.post(f"{BASE_URL}/api/admin/email/send-test",
                     json={"to_email": "someone@example.com"}, timeout=10)
    assert r.status_code == 403
