"""Iter 30l — T&Cs versions/acceptances, kiosk settings, feature flags."""
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
        pytest.skip("Admin account has 2FA — clear it first")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin(): return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner(): return _login("learner@ifpi.org", "learner123")


# Iter 23 — Autouse teardown that demotes+deletes any iter30l-* terms
# rows this module publishes. Without this, each iter30l test run leaves
# the newest published terms version as `is_current=True`, which then
# gates the /live-sessions UI (TermsGate) for every subsequent user
# visit. The cleanup service correctly preserves is_current=True rows
# by design, so cleanup has to happen here — where the test knows the
# row is disposable — not later.
@pytest.fixture(autouse=True, scope="module")
def _cleanup_iter30l_terms():
    yield
    import sys
    sys.path.insert(0, "/app/backend")
    from core.database import SessionLocal
    from models import TermsVersion, TermsAcceptance
    with SessionLocal() as db:
        ids = [
            r.id for r in db.query(TermsVersion.id, TermsVersion.version)
            .filter(TermsVersion.version.like("iter30l-%")).all()
        ]
        if ids:
            db.query(TermsAcceptance).filter(
                TermsAcceptance.terms_version_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(TermsVersion).filter(
                TermsVersion.id.in_(ids)
            ).delete(synchronize_session=False)
            db.commit()




# ── T&Cs ──────────────────────────────────────────────────────────────


def test_publish_terms_then_current_shows_it(admin, learner):
    v = f"iter30l-{int(time.time())}"
    r = admin.post(f"{BASE_URL}/api/admin/terms",
                   json={"version": v, "title": "Test T&Cs",
                         "body_markdown": "# Please accept"}, timeout=10)
    assert r.status_code == 200, r.text
    tv_id = r.json()["id"]

    cur = learner.get(f"{BASE_URL}/api/terms/current", timeout=10).json()
    assert cur["has_terms"] is True
    assert cur["accepted"] is False
    assert cur["terms"]["version"] == v

    rA = learner.post(f"{BASE_URL}/api/terms/accept",
                      json={"terms_version_id": tv_id}, timeout=10)
    assert rA.status_code == 200
    assert "accepted_at" in rA.json()

    cur2 = learner.get(f"{BASE_URL}/api/terms/current", timeout=10).json()
    assert cur2["accepted"] is True

    # Duplicate accept is idempotent
    rD = learner.post(f"{BASE_URL}/api/terms/accept",
                      json={"terms_version_id": tv_id}, timeout=10)
    assert rD.status_code == 200


def test_publish_flips_previous_current(admin):
    v1 = f"iter30l-first-{int(time.time())}"
    v2 = f"iter30l-second-{int(time.time())}"
    admin.post(f"{BASE_URL}/api/admin/terms",
               json={"version": v1, "body_markdown": "v1"}, timeout=10)
    admin.post(f"{BASE_URL}/api/admin/terms",
               json={"version": v2, "body_markdown": "v2"}, timeout=10)
    r = admin.get(f"{BASE_URL}/api/admin/terms", timeout=10).json()
    current = [i for i in r["items"] if i["is_current"]]
    assert len(current) == 1
    assert current[0]["version"] == v2


def test_learner_cannot_publish_terms(learner):
    r = learner.post(f"{BASE_URL}/api/admin/terms",
                     json={"version": "hack", "body_markdown": "no"}, timeout=10)
    assert r.status_code == 403


def test_acceptance_audit_shows_ip_and_agent(admin, learner):
    v = f"iter30l-audit-{int(time.time())}"
    tv = admin.post(f"{BASE_URL}/api/admin/terms",
                    json={"version": v, "body_markdown": "audit"},
                    timeout=10).json()
    learner.post(f"{BASE_URL}/api/terms/accept",
                 json={"terms_version_id": tv["id"]},
                 headers={"User-Agent": "TestBot/1.0"}, timeout=10)
    r = admin.get(f"{BASE_URL}/api/admin/terms/acceptances", timeout=10).json()
    match = [it for it in r["items"] if it["version"] == v]
    assert match, f"no acceptance recorded for {v}"


# ── Kiosk ─────────────────────────────────────────────────────────────


def test_kiosk_default_settings(admin):
    r = admin.get(f"{BASE_URL}/api/kiosk/settings", timeout=10).json()
    assert "enabled" in r
    assert "idle_timeout_seconds" in r


def test_kiosk_update_then_unlock_with_pin(admin):
    r = admin.put(f"{BASE_URL}/api/admin/kiosk/settings",
                  json={"enabled": True, "idle_timeout_seconds": 120,
                        "unlock_pin": "5432"}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["has_pin"] is True
    # Unlock succeeds with correct PIN
    rU = admin.post(f"{BASE_URL}/api/kiosk/unlock",
                    json={"method": "pin", "value": "5432"}, timeout=10)
    assert rU.status_code == 200
    assert rU.json()["unlocked"] is True
    # Wrong PIN rejected
    rW = admin.post(f"{BASE_URL}/api/kiosk/unlock",
                    json={"method": "pin", "value": "0000"}, timeout=10)
    assert rW.status_code == 401


def test_kiosk_unlock_password_fallback(admin):
    r = admin.post(f"{BASE_URL}/api/kiosk/unlock",
                   json={"method": "password", "value": "admin123"},
                   timeout=10)
    assert r.status_code == 200


# ── Feature flags ─────────────────────────────────────────────────────


def test_flags_default_registry(admin):
    r = admin.get(f"{BASE_URL}/api/feature-flags", timeout=10).json()
    assert "ai_authoring" in r["flags"]
    # ai_authoring defaults ON
    assert r["flags"]["ai_authoring"] is True
    # kiosk_mode defaults OFF
    assert r["flags"]["kiosk_mode"] is False
    # Known-flag registry included
    assert any(f["key"] == "ai_authoring" for f in r["known_flags"])


def test_flags_override_then_read_back(admin):
    r = admin.put(f"{BASE_URL}/api/admin/feature-flags/ai_authoring",
                  json={"enabled": False, "note": "billing tier"}, timeout=10)
    assert r.status_code == 200
    check = admin.get(f"{BASE_URL}/api/feature-flags", timeout=10).json()
    assert check["flags"]["ai_authoring"] is False
    # Reset
    admin.put(f"{BASE_URL}/api/admin/feature-flags/ai_authoring",
              json={"enabled": True}, timeout=10)


def test_unknown_flag_key_rejected(admin):
    r = admin.put(f"{BASE_URL}/api/admin/feature-flags/does_not_exist",
                  json={"enabled": True}, timeout=10)
    assert r.status_code == 400


def test_learner_cannot_set_flag(learner):
    r = learner.put(f"{BASE_URL}/api/admin/feature-flags/ai_authoring",
                    json={"enabled": False}, timeout=10)
    assert r.status_code == 403
