"""Iter 25 — Marketplace analytics roll-up + subscription secret rotation
+ QR code endpoint tests.

Covers:
- GET /api/admin/marketplace-funnel (roll-up, no course_id) returns
  totals + top_by_conversion + daily arrays.
- Rotation: POST /api/live-sessions/subscribe-url/rotate bumps the
  org's secret_version. Old URLs immediately 401. New URL from
  /subscribe-url returns a token whose payload sv matches the new version.
- Rotation does NOT log out the user (JWT still valid).
- Learners cannot rotate.
- QR endpoint returns image/svg+xml with real SVG content.
- QR endpoint refuses admin kind for learner role.
"""
from __future__ import annotations

import os
import sys

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    r.raise_for_status()
    tok = r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def learner():
    return _login(LEARNER)


# ── Roll-up ──────────────────────────────────────────────────────────
def test_rollup_returns_expected_shape(admin):
    r = admin.get(f"{BASE_URL}/api/admin/marketplace-funnel", timeout=10)
    assert r.status_code == 200
    d = r.json()
    for key in ("days_window", "totals", "view_to_enroll_rate",
                "enroll_to_complete_rate", "top_by_conversion", "daily"):
        assert key in d, f"missing key {key}"
    assert set(d["totals"].keys()) >= {"views", "enrollments", "completions",
                                       "courses_with_activity"}
    assert isinstance(d["top_by_conversion"], list)
    assert len(d["daily"]) == d["days_window"] + 1


def test_rollup_rates_bounded_and_clamped(admin):
    # Seed a view so views > 0
    requests.post(f"{BASE_URL}/api/catalog/1/track-view", json={}, timeout=10)
    r = admin.get(f"{BASE_URL}/api/admin/marketplace-funnel?days=365", timeout=10)
    d = r.json()
    assert 0.0 <= d["view_to_enroll_rate"] <= 1.0
    assert 0.0 <= d["enroll_to_complete_rate"] <= 1.0
    for row in d["top_by_conversion"]:
        assert 0.0 <= row["view_to_enroll_rate"] <= 1.0


def test_rollup_top_by_conversion_sorted_desc(admin):
    r = admin.get(f"{BASE_URL}/api/admin/marketplace-funnel", timeout=10).json()
    rates = [row["view_to_enroll_rate"] for row in r["top_by_conversion"]]
    assert rates == sorted(rates, reverse=True)


def test_rollup_learner_forbidden(learner):
    r = learner.get(f"{BASE_URL}/api/admin/marketplace-funnel", timeout=10)
    assert r.status_code == 403


# ── Secret rotation ──────────────────────────────────────────────────
def test_rotation_bumps_version_and_invalidates_old_url(admin):
    # Get current URL
    r1 = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10).json()
    old_token = r1["token"]
    old_sv = r1["secret_version"]

    # Old URL works
    anon = requests.Session()
    ok = anon.get(f"{BASE_URL}/api/live-sessions/subscribe/{old_token}.ics", timeout=10)
    assert ok.status_code == 200

    # Rotate
    rot = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url/rotate", timeout=10)
    assert rot.status_code == 200
    d = rot.json()
    assert d["new_version"] == d["old_version"] + 1
    assert d["new_version"] == old_sv + 1

    # Old URL now 401
    bad = anon.get(f"{BASE_URL}/api/live-sessions/subscribe/{old_token}.ics", timeout=10)
    assert bad.status_code == 401
    assert "revoked" in (bad.json().get("detail", "")
                          or bad.json().get("error", {}).get("message", "")).lower()

    # Fresh URL works
    r2 = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10).json()
    assert r2["secret_version"] == old_sv + 1
    assert r2["token"] != old_token
    ok2 = anon.get(f"{BASE_URL}/api/live-sessions/subscribe/{r2['token']}.ics", timeout=10)
    assert ok2.status_code == 200


def test_rotation_does_not_log_out_admin(admin):
    """After rotation, the admin's regular API calls must keep working —
    rotating subscription_secret_version must NOT invalidate JWT_SECRET."""
    admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url/rotate", timeout=10)
    r = admin.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@ifpi.org"


def test_rotation_learner_forbidden(learner):
    r = learner.post(f"{BASE_URL}/api/live-sessions/subscribe-url/rotate", timeout=10)
    assert r.status_code == 403


# ── QR endpoint ──────────────────────────────────────────────────────
def test_qr_returns_svg(admin):
    r = admin.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr?kind=admin", timeout=10)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    body = r.text
    assert body.startswith("<?xml") or body.startswith("<svg")
    assert "<svg" in body


def test_qr_learner_can_get_own_kind(learner):
    r = learner.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr?kind=learner", timeout=10)
    assert r.status_code == 200


def test_qr_learner_cannot_get_admin_kind(learner):
    r = learner.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr?kind=admin", timeout=10)
    assert r.status_code == 403


def test_qr_regenerated_on_secret_rotation(admin):
    """Two QR SVGs before + after rotation must differ (different token
    encoded)."""
    admin.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr?kind=admin", timeout=10)
    before = admin.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr?kind=admin", timeout=10).text
    admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url/rotate", timeout=10)
    after = admin.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr?kind=admin", timeout=10).text
    assert before != after, "QR must change after secret rotation"
