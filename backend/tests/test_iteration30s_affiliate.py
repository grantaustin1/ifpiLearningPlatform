"""Iter 30s — Affiliate / referral program."""
from __future__ import annotations

import os
import time

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
        pytest.skip("2FA on")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin(): return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner(): return _login("learner@ifpi.org", "learner123")


def test_create_code_auto_generates(admin):
    r = admin.post(f"{BASE_URL}/api/admin/affiliate/codes",
                   json={"reward_bps": 1200}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["code"]) == 8
    assert body["reward_bps"] == 1200
    assert body["reward_pct"] == 12.0
    assert body["is_active"] is True


def test_create_code_with_custom_string(admin):
    slug = f"TEST{int(time.time())}"
    r = admin.post(f"{BASE_URL}/api/admin/affiliate/codes",
                   json={"code": slug, "reward_bps": 1000}, timeout=10)
    assert r.status_code == 200
    assert r.json()["code"] == slug.upper()


def test_reject_out_of_bounds_reward(admin):
    r = admin.post(f"{BASE_URL}/api/admin/affiliate/codes",
                   json={"reward_bps": 99}, timeout=10)  # < 100
    assert r.status_code == 422
    r2 = admin.post(f"{BASE_URL}/api/admin/affiliate/codes",
                    json={"reward_bps": 5001}, timeout=10)  # > 5000
    assert r2.status_code == 422


def test_public_lookup_returns_referrer_name(admin):
    # Create a code, then look it up publicly
    c = admin.post(f"{BASE_URL}/api/admin/affiliate/codes",
                   json={"reward_bps": 1000}, timeout=10).json()
    r = requests.get(f"{BASE_URL}/api/affiliate/lookup/{c['code']}", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["referrer_org_name"]


def test_public_lookup_missing_code_404():
    r = requests.get(f"{BASE_URL}/api/affiliate/lookup/DOES-NOT-EXIST", timeout=10)
    assert r.status_code == 404


def test_deactivate_code_hides_from_lookup(admin):
    c = admin.post(f"{BASE_URL}/api/admin/affiliate/codes",
                   json={"reward_bps": 1000}, timeout=10).json()
    # Now deactivate
    p = admin.patch(f"{BASE_URL}/api/admin/affiliate/codes/{c['id']}",
                    json={"is_active": False}, timeout=10)
    assert p.status_code == 200
    r = requests.get(f"{BASE_URL}/api/affiliate/lookup/{c['code']}", timeout=10)
    assert r.status_code == 404


def test_earnings_shape(admin):
    r = admin.get(f"{BASE_URL}/api/admin/affiliate/earnings", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "total_credited_cents" in body
    assert "total_pending_cents" in body
    assert "by_status" in body


def test_referrals_list_shape(admin):
    r = admin.get(f"{BASE_URL}/api/admin/affiliate/referrals", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)


def test_learner_forbidden(learner):
    r = learner.get(f"{BASE_URL}/api/admin/affiliate/codes", timeout=10)
    assert r.status_code == 403
    r2 = learner.post(f"{BASE_URL}/api/admin/affiliate/codes",
                      json={"reward_bps": 1000}, timeout=10)
    assert r2.status_code == 403
