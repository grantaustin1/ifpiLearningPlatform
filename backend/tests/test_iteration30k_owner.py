"""Iter 30k — Members needing action widget endpoint."""
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
        pytest.skip("Admin account has 2FA — disable it before running these tests")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin():
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner():
    return _login("learner@ifpi.org", "learner123")


def test_widget_shape_and_admin_gate(admin, learner):
    """Admin gets a scoped list, learner gets 403."""
    r = admin.get(f"{BASE_URL}/api/admin/dashboard/members-needing-action",
                  timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "count" in body
    assert "total_flagged" in body
    assert "generated_at" in body
    assert isinstance(body["items"], list)
    # Learner is blocked
    rL = learner.get(f"{BASE_URL}/api/admin/dashboard/members-needing-action",
                     timeout=10)
    assert rL.status_code == 403


def test_widget_item_shape(admin):
    r = admin.get(
        f"{BASE_URL}/api/admin/dashboard/members-needing-action?limit=5",
        timeout=10)
    body = r.json()
    for it in body["items"]:
        assert set(it.keys()) >= {
            "user_id", "email", "name", "reason_code", "reason",
            "detail", "next_step", "priority"
        }
        assert it["reason_code"] in {"STALLED", "IDLE", "NEVER_SIGNED_IN"}
        assert it["priority"] in {1, 2, 3}
        assert it["next_step"]["label"]
        assert it["next_step"]["path"].startswith("/")


def test_limit_enforced(admin):
    r = admin.get(
        f"{BASE_URL}/api/admin/dashboard/members-needing-action?limit=3",
        timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 3


def test_ordering_by_priority(admin):
    """Priority 1 (STALLED) items MUST come before Priority 2 (IDLE)
    which come before Priority 3 (NEVER_SIGNED_IN)."""
    r = admin.get(
        f"{BASE_URL}/api/admin/dashboard/members-needing-action?limit=100",
        timeout=10)
    body = r.json()
    priorities = [it["priority"] for it in body["items"]]
    assert priorities == sorted(priorities), (
        f"items not priority-sorted: {priorities}"
    )
