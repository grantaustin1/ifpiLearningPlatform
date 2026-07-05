"""Iter 30o/30p — Onboarding checklist + Scheduled reports."""
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
        pytest.skip("2FA enabled — clear first")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin(): return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner(): return _login("learner@ifpi.org", "learner123")


# ── Onboarding ─────────────────────────────────────────────────────────


def test_onboarding_shape(admin):
    r = admin.get(f"{BASE_URL}/api/admin/onboarding/checklist", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["steps"], list)
    assert body["percent"] >= 0
    assert body["completed"] <= body["total"]


def test_onboarding_step_keys_stable(admin):
    """The set of step keys is a public contract used by the frontend."""
    r = admin.get(f"{BASE_URL}/api/admin/onboarding/checklist", timeout=10).json()
    keys = {s["key"] for s in r["steps"]}
    expected = {"branding", "course", "invite", "cert", "smtp", "terms", "activity"}
    assert expected.issubset(keys), f"missing keys: {expected - keys}"


def test_onboarding_learner_forbidden(learner):
    r = learner.get(f"{BASE_URL}/api/admin/onboarding/checklist", timeout=10)
    assert r.status_code == 403


# ── Scheduled reports ─────────────────────────────────────────────────


def test_scheduled_reports_crud_cycle(admin):
    # Create
    r = admin.post(f"{BASE_URL}/api/admin/scheduled-reports",
                   json={"report_kind": "enrollment_summary",
                         "cadence": "weekly",
                         "recipient_emails": ["admin@ifpi.org"]},
                   timeout=10)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    # List includes it
    ls = admin.get(f"{BASE_URL}/api/admin/scheduled-reports", timeout=10).json()
    assert any(it["id"] == rid for it in ls["items"])
    # Update
    up = admin.put(f"{BASE_URL}/api/admin/scheduled-reports/{rid}",
                   json={"report_kind": "enrollment_summary",
                         "cadence": "daily",
                         "recipient_emails": ["admin@ifpi.org"],
                         "is_active": False},
                   timeout=10)
    assert up.status_code == 200
    assert up.json()["cadence"] == "daily"
    assert up.json()["is_active"] is False
    # Delete
    d = admin.delete(f"{BASE_URL}/api/admin/scheduled-reports/{rid}",
                     timeout=10)
    assert d.status_code == 200


def test_scheduled_reports_reject_unknown_kind(admin):
    r = admin.post(f"{BASE_URL}/api/admin/scheduled-reports",
                   json={"report_kind": "bogus_report",
                         "cadence": "weekly",
                         "recipient_emails": ["a@b.c"]},
                   timeout=10)
    assert r.status_code == 422


def test_scheduled_reports_reject_bad_email(admin):
    r = admin.post(f"{BASE_URL}/api/admin/scheduled-reports",
                   json={"report_kind": "enrollment_summary",
                         "cadence": "weekly",
                         "recipient_emails": ["not-an-email"]},
                   timeout=10)
    assert r.status_code == 422


def test_scheduled_reports_run_now_enqueues(admin):
    rc = admin.post(f"{BASE_URL}/api/admin/scheduled-reports",
                    json={"report_kind": "enrollment_summary",
                          "cadence": "weekly",
                          "recipient_emails": ["admin@ifpi.org"]},
                    timeout=10).json()
    r = admin.post(f"{BASE_URL}/api/admin/scheduled-reports/{rc['id']}/run-now",
                   timeout=10)
    assert r.status_code == 200
    assert r.json()["queued"] is True
    admin.delete(f"{BASE_URL}/api/admin/scheduled-reports/{rc['id']}", timeout=10)


def test_scheduled_reports_learner_forbidden(learner):
    r = learner.get(f"{BASE_URL}/api/admin/scheduled-reports", timeout=10)
    assert r.status_code == 403
    r2 = learner.post(f"{BASE_URL}/api/admin/scheduled-reports",
                      json={"report_kind": "enrollment_summary",
                            "cadence": "weekly",
                            "recipient_emails": ["x@y.z"]},
                      timeout=10)
    assert r2.status_code == 403
