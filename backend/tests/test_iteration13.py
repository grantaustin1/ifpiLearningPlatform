"""Iteration 13 backend tests — Weekly cohort digest.

Covers:
  - Org GET exposes new fields (cohort_digest_enabled, cohort_digest_last_sent_at)
  - PUT cohort-settings accepts and persists digest_enabled toggle
  - POST /cohort-digest/send-now queues an email per admin + sets last_sent_at
  - send-now writes COHORT_DIGEST_SENT audit row
  - LEARNER forbidden from send-now
  - compute_org_digest buckets cohorts correctly (past / nudge / other)
  - send_weekly_digests skips disabled orgs and recently-sent orgs
"""
from __future__ import annotations

import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    time.sleep(1.5)
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def learner_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    time.sleep(1.5)
    r = s.post(f"{BASE_URL}/api/auth/login", json=LEARNER)
    assert r.status_code == 200, f"learner login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


class TestDigestSettings:
    def test_get_org_includes_new_fields(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/organization")
        assert r.status_code == 200
        d = r.json()
        assert "cohort_digest_enabled" in d
        assert "cohort_digest_last_sent_at" in d
        assert isinstance(d["cohort_digest_enabled"], bool)

    def test_put_persists_digest_toggle(self, admin_client):
        # Disable
        r = admin_client.put(f"{BASE_URL}/api/organization/cohort-settings",
                             json={"cohort_threshold": 75,
                                   "cohort_celebration_webhook_url": None,
                                   "cohort_digest_enabled": False})
        assert r.status_code == 200, r.text
        d = admin_client.get(f"{BASE_URL}/api/organization").json()
        assert d["cohort_digest_enabled"] is False
        # Re-enable
        r2 = admin_client.put(f"{BASE_URL}/api/organization/cohort-settings",
                              json={"cohort_threshold": 75,
                                    "cohort_celebration_webhook_url": None,
                                    "cohort_digest_enabled": True})
        assert r2.status_code == 200
        d2 = admin_client.get(f"{BASE_URL}/api/organization").json()
        assert d2["cohort_digest_enabled"] is True

    def test_put_without_digest_field_does_not_change_it(self, admin_client):
        # Make sure leaving it out of the payload preserves existing value
        admin_client.put(f"{BASE_URL}/api/organization/cohort-settings",
                         json={"cohort_threshold": 75,
                               "cohort_celebration_webhook_url": None,
                               "cohort_digest_enabled": True})
        # Omit cohort_digest_enabled in next PUT
        r = admin_client.put(f"{BASE_URL}/api/organization/cohort-settings",
                             json={"cohort_threshold": 80,
                                   "cohort_celebration_webhook_url": None})
        assert r.status_code == 200
        d = admin_client.get(f"{BASE_URL}/api/organization").json()
        assert d["cohort_threshold"] == 80
        # Still True — was not in the payload, should be unchanged
        assert d["cohort_digest_enabled"] is True


class TestSendNow:
    def test_learner_forbidden(self, learner_client):
        r = learner_client.post(f"{BASE_URL}/api/organization/cohort-digest/send-now")
        assert r.status_code in (401, 403)

    def test_admin_send_now_returns_counts(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/organization/cohort-digest/send-now")
        assert r.status_code == 200, r.text
        body = r.json()
        # Shape contract
        for k in ("queued", "total_cohorts", "past", "nudge", "threshold"):
            assert k in body, f"missing key {k}"
        # At least one admin in the IFPI org → queued ≥ 1
        assert body["queued"] >= 1
        assert body["threshold"] >= 1 and body["threshold"] <= 100

    def test_last_sent_at_updated(self, admin_client):
        # Fire it
        admin_client.post(f"{BASE_URL}/api/organization/cohort-digest/send-now")
        d = admin_client.get(f"{BASE_URL}/api/organization").json()
        assert d["cohort_digest_last_sent_at"] is not None

    def test_audit_row_written(self, admin_client):
        admin_client.post(f"{BASE_URL}/api/organization/cohort-digest/send-now")
        r = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                             params={"action": "COHORT_DIGEST_SENT", "limit": 5})
        assert r.status_code == 200
        items = r.json().get("items") or r.json().get("data") or []
        assert len(items) >= 1
        last = items[0]
        assert last["action"] == "COHORT_DIGEST_SENT"
        meta = last.get("metadata") or {}
        for k in ("admin_count", "cohort_count", "threshold"):
            assert k in meta


class TestDigestService:
    """Service-level tests — run in-process for richer assertions."""

    def test_compute_buckets_cohorts(self):
        # Use the actual DB the API uses
        from core.database import SessionLocal
        from models import Organization
        from services.cohort_digest import compute_org_digest

        with SessionLocal() as db:
            org = db.query(Organization).filter(Organization.slug == "ifpi-main").first()
            assert org is not None
            payload = compute_org_digest(db, org)
            assert "threshold" in payload
            assert "past" in payload and "nudge" in payload and "other" in payload
            assert isinstance(payload["total_cohorts"], int)
            # past + nudge + other should equal total_cohorts (no double counting)
            assert (len(payload["past"]) + len(payload["nudge"]) + len(payload["other"])) == payload["total_cohorts"]

    def test_weekly_digest_skips_disabled_org(self):
        from datetime import datetime, timezone
        from core.database import SessionLocal
        from models import Organization
        from services.cohort_digest import send_weekly_digests

        with SessionLocal() as db:
            org = db.query(Organization).filter(Organization.slug == "ifpi-main").first()
            assert org is not None
            org.cohort_digest_enabled = False
            db.commit()
            total = send_weekly_digests(db)
            # No emails should have been queued for the only org
            assert total == 0
            # Restore
            org.cohort_digest_enabled = True
            db.commit()

    def test_weekly_digest_dedupes_recent_sends(self):
        from datetime import datetime, timezone
        from core.database import SessionLocal
        from models import Organization
        from services.cohort_digest import send_weekly_digests, send_digest_for_org

        with SessionLocal() as db:
            org = db.query(Organization).filter(Organization.slug == "ifpi-main").first()
            assert org is not None
            org.cohort_digest_enabled = True
            # Fire one send to set last_sent_at to now
            send_digest_for_org(db, org)
            db.commit()
            # Immediate second run via weekly path should skip (within 6 days)
            total = send_weekly_digests(db)
            assert total == 0
