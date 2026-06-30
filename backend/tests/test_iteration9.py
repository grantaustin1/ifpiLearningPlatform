"""Iteration 9 backend tests:
- Cohort widget endpoints
- Cohort celebrations (check_cohorts idempotency + first-fire)
- Alembic head a9c2470b8e15 idempotency / downgrade-upgrade
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://code-quality-check-31.preview.emergentagent.com").rstrip("/")
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"}, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def learner_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Space out from admin login to avoid IP-based brute-force lockout
    time.sleep(1.2)
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "learner@ifpi.org", "password": "learner123"}, timeout=20)
    assert r.status_code == 200, r.text
    return s


# --- BACKEND COHORT ENDPOINTS ---------------------------------------------

class TestCohortReportEndpoints:
    def test_cohorts_list(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/cohorts", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)
        # AGENT008 seeded from prior agent_008 run
        names = [c.get("cohort") for c in body]
        if "AGENT008" not in names:
            pytest.skip(f"AGENT008 cohort not present in this environment: {names}")
        ag = next(c for c in body if c["cohort"] == "AGENT008")
        assert ag.get("learner_count", 0) >= 1

    def test_cohort_stats_unfiltered(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/reports/cohort-stats", timeout=20)
        assert r.status_code == 200, r.text
        b = r.json()
        for k in ("learners", "enrollments", "completions", "completion_rate",
                  "avg_exam_score", "certificates_issued", "badges_earned"):
            assert k in b, f"missing key {k}"

    def test_cohort_stats_agent008(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/reports/cohort-stats",
                             params={"cohort": "AGENT008"}, timeout=20)
        assert r.status_code == 200, r.text
        b = r.json()
        if b["learners"] == 0:
            pytest.skip("AGENT008 cohort has no learners in this environment")
        assert b["learners"] >= 1
        assert b["enrollments"] >= 1
        assert b["completion_rate"] >= 0
        assert "avg_exam_score" in b
        assert "certificates_issued" in b
        assert "badges_earned" in b

    def test_cohort_stats_unknown_returns_zeros(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/reports/cohort-stats",
                             params={"cohort": "TEST_DOES_NOT_EXIST_XYZ"}, timeout=20)
        assert r.status_code == 200
        b = r.json()
        assert b["learners"] == 0
        assert b["enrollments"] == 0

    def test_analytics_still_works(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/analytics", timeout=20)
        assert r.status_code == 200
        b = r.json()
        for k in ("total_learners", "total_courses", "total_certificates",
                  "total_exam_attempts", "monthly_enrollments"):
            assert k in b


# --- COHORT CELEBRATIONS --------------------------------------------------

class TestCohortCelebrations:
    def test_check_cohorts_idempotent_or_first_fire(self):
        """The previous run already fired AGENT008 once. Run check_cohorts:
        if a prior celebration audit row exists → returns 0 (idempotency).
        Else → returns >=1 (first fire) and second call returns 0.
        """
        sys.path.insert(0, BACKEND_DIR)
        from core.database import SessionLocal
        from services.cohort_celebrations import check_cohorts
        from models import AuditLog, OutboxMessage

        with SessionLocal() as db:
            from models import User
            cohort_users = db.query(User).filter(User.cohort == "AGENT008").count()
            if cohort_users == 0:
                pytest.skip("AGENT008 cohort users not present in this environment")
            prior = db.query(AuditLog).filter(
                AuditLog.action == "COHORT_MILESTONE_REACHED",
                AuditLog.target_id == "AGENT008",
            ).count()

            if prior == 0:
                outbox_before = db.query(OutboxMessage).filter(
                    OutboxMessage.template == "cohort_milestone").count()
                fired1 = check_cohorts(db)
                assert fired1 >= 1, f"expected first-fire ≥1, got {fired1}"
                # Audit row exists
                after = db.query(AuditLog).filter(
                    AuditLog.action == "COHORT_MILESTONE_REACHED",
                    AuditLog.target_id == "AGENT008",
                ).count()
                assert after == 1, f"expected exactly 1 AGENT008 audit row, got {after}"
                # Outbox queued for at least one admin
                outbox_after = db.query(OutboxMessage).filter(
                    OutboxMessage.template == "cohort_milestone").count()
                assert outbox_after > outbox_before, "no cohort_milestone outbox emails queued"
                # Now idempotent
                fired2 = check_cohorts(db)
                assert fired2 == 0, f"expected idempotent 0 on 2nd call, got {fired2}"
            else:
                # already celebrated previously — must be idempotent (return 0)
                fired = check_cohorts(db)
                assert fired == 0, (
                    f"expected idempotent 0 (prior audit row exists, count={prior}), got {fired}")


# --- ALEMBIC MIGRATIONS ---------------------------------------------------

class TestAlembic:
    def _alembic(self, *args):
        return subprocess.run(
            ["alembic", *args], capture_output=True, text=True,
            cwd=BACKEND_DIR, timeout=60,
        )

    def test_current_head(self):
        r = self._alembic("current")
        assert r.returncode == 0, r.stderr
        # head can be displayed as 'a9c2470b8e15 (head)'
        # Accept current head or any later revision (CI safety)
        out = r.stdout + r.stderr
        assert any(h in out for h in ("a9c2470b8e15", "b3d8915cef27")), f"out={r.stdout} err={r.stderr}"

    def test_upgrade_head_idempotent(self):
        r = self._alembic("upgrade", "head")
        assert r.returncode == 0, f"out={r.stdout} err={r.stderr}"

    def test_downgrade_one_then_upgrade(self):
        r = self._alembic("downgrade", "-1")
        assert r.returncode == 0, f"downgrade out={r.stdout} err={r.stderr}"
        r2 = self._alembic("upgrade", "head")
        assert r2.returncode == 0, f"reupgrade out={r2.stdout} err={r2.stderr}"
        r3 = self._alembic("current")
        assert any(h in (r3.stdout + r3.stderr) for h in ("a9c2470b8e15", "b3d8915cef27"))


# --- LOGIN REGRESSION -----------------------------------------------------

class TestLogins:
    def test_admin_login(self, admin_client):
        # If fixture succeeded, this passes by definition. Hit /me for proof.
        r = admin_client.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "admin@ifpi.org"

    def test_learner_login(self, learner_client):
        r = learner_client.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == "learner@ifpi.org"
