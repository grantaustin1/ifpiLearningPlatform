"""Iteration 8 backend tests — audit log, cohorts, cohort-stats, transcript PDF.

Run with:
  cd /app/backend && python -m pytest tests/test_iteration8.py -v
"""
import os
import sqlite3
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    import pytest
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests", allow_module_level=True)
SQLITE_PATH = "/app/backend/ifpi_lms.db"

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def admin_client():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def learner_client():
    return _login(LEARNER)


# ── Audit log API ─────────────────────────────────────────────────────
class TestAuditLog:
    def test_admin_audit_log_shape(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/audit-log")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total" in data and "items" in data
        assert isinstance(data["items"], list)
        if data["items"]:
            item = data["items"][0]
            for k in ("id", "action", "target_type", "target_id", "metadata",
                      "ip_address", "actor", "created_at"):
                assert k in item, f"missing {k} in audit item"

    def test_learner_forbidden(self, learner_client):
        r = learner_client.get(f"{BASE_URL}/api/admin/audit-log")
        assert r.status_code == 403

    def test_audit_filter_by_action(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                             params={"action": "THEME_APPLIED"})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["action"] == "THEME_APPLIED"


# ── Bulk invite writes audit + propagates cohort ──────────────────────
class TestBulkInviteAudit:
    def test_bulk_invite_writes_audit_with_cohort(self, admin_client):
        cohort = f"Q1-2026-TEST-{int(time.time())}"
        emails = [f"TEST_bulk_audit_{int(time.time())}_a@example.com",
                  f"TEST_bulk_audit_{int(time.time())}_b@example.com"]
        payload = {"invitations": [{"email": e, "role": "LEARNER"} for e in emails],
                   "cohort": cohort}
        r = admin_client.post(f"{BASE_URL}/api/admin/invitations/bulk", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["queued"] == 2

        # Fetch audit log and look for matching entry
        time.sleep(0.4)
        r2 = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                              params={"action": "INVITATIONS_BULK_QUEUED", "limit": 25})
        assert r2.status_code == 200
        items = r2.json()["items"]
        match = [it for it in items if it["metadata"].get("cohort") == cohort]
        assert match, f"No audit entry with cohort={cohort} found in: {items[:3]}"
        a = match[0]
        assert a["action"] == "INVITATIONS_BULK_QUEUED"
        assert a["metadata"].get("queued") == 2
        assert a["actor"] and a["actor"]["email"] == ADMIN["email"]


# ── Theme apply writes audit ──────────────────────────────────────────
class TestThemeAudit:
    def test_theme_apply_audit(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/organization/apply-theme/crimson_gold")
        assert r.status_code == 200, r.text
        time.sleep(0.3)
        r2 = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                              params={"action": "THEME_APPLIED", "limit": 5})
        items = r2.json()["items"]
        assert items, "no THEME_APPLIED audit row found"
        # latest entry should be crimson_gold
        latest = items[0]
        assert latest["metadata"].get("preset") == "crimson_gold"


# ── Badge tier mutations write audit ──────────────────────────────────
class TestBadgeTierAudit:
    def test_create_update_delete_writes_audit(self, admin_client):
        slug = f"TEST_AUDIT_TIER_{int(time.time())}"
        r = admin_client.post(f"{BASE_URL}/api/badge-tiers", json={
            "slug": slug, "label": "Audit tier", "emoji": "🧪",
            "threshold_xp": 33, "is_active": True,
        })
        assert r.status_code == 201, r.text
        tier_id = r.json()["id"]

        r = admin_client.patch(f"{BASE_URL}/api/badge-tiers/{tier_id}",
                               json={"label": "Audit tier v2"})
        assert r.status_code == 200

        r = admin_client.delete(f"{BASE_URL}/api/badge-tiers/{tier_id}")
        assert r.status_code in (200, 204)

        time.sleep(0.3)
        # Pull last 50 events and ensure we see all three action types since now
        r2 = admin_client.get(f"{BASE_URL}/api/admin/audit-log", params={"limit": 200})
        items = r2.json()["items"]
        actions_seen = {it["action"] for it in items if it["target_id"] == str(tier_id)}
        assert "BADGE_TIER_CREATED" in actions_seen, actions_seen
        assert "BADGE_TIER_UPDATED" in actions_seen, actions_seen
        assert "BADGE_TIER_DELETED" in actions_seen, actions_seen

    def test_reorder_writes_audit(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/badge-tiers")
        tiers = r.json()
        original = [t["id"] for t in tiers]
        if len(original) < 2:
            pytest.skip("need 2+ tiers to test reorder")
        reordered = list(reversed(original))
        r = admin_client.patch(f"{BASE_URL}/api/badge-tiers/reorder",
                               json={"order": reordered})
        assert r.status_code == 200, r.text
        # restore
        admin_client.patch(f"{BASE_URL}/api/badge-tiers/reorder", json={"order": original})

        time.sleep(0.3)
        r2 = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                              params={"action": "BADGE_TIERS_REORDERED", "limit": 5})
        assert r2.json()["items"], "no BADGE_TIERS_REORDERED row"


# ── SMTP update writes audit ──────────────────────────────────────────
class TestSmtpAudit:
    def test_smtp_put_writes_audit(self, admin_client):
        # Pull current to restore
        r0 = admin_client.get(f"{BASE_URL}/api/organization/smtp")
        assert r0.status_code == 200
        current = r0.json()
        # PUT something harmless
        r = admin_client.put(f"{BASE_URL}/api/organization/smtp", json={
            "smtp_host": current.get("smtp_host") or "",
            "smtp_port": current.get("smtp_port") or 587,
            "smtp_use_tls": bool(current.get("smtp_use_tls", True)),
            "smtp_username": current.get("smtp_username") or "",
            "smtp_from_email": current.get("smtp_from_email") or "",
            "smtp_from_name": current.get("smtp_from_name") or "",
        })
        assert r.status_code in (200, 204), r.text
        time.sleep(0.3)
        r2 = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                              params={"action": "SMTP_CONFIG_UPDATED", "limit": 5})
        assert r2.json()["items"], "no SMTP_CONFIG_UPDATED row"


# ── Academy create writes audit ───────────────────────────────────────
class TestAcademyAudit:
    def test_create_academy_writes_audit(self, admin_client):
        ts = int(time.time())
        payload = {
            "name": f"TEST Academy Audit {ts}",
            "slug": f"test-acad-audit-{ts}",
            "admin_email": f"TEST_acad_audit_{ts}@example.com",
            "admin_name": "Audit Admin",
        }
        r = admin_client.post(f"{BASE_URL}/api/academies", json=payload)
        assert r.status_code in (200, 201), r.text
        time.sleep(0.3)
        r2 = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                              params={"action": "ACADEMY_CREATED", "limit": 5})
        items = r2.json()["items"]
        # Note: audit is written under caller's org. Verify at least one entry exists.
        assert items, "no ACADEMY_CREATED row"


# ── Cohorts ───────────────────────────────────────────────────────────
class TestCohorts:
    def test_list_cohorts_endpoint(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/cohorts")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for row in data:
            assert "cohort" in row and "learner_count" in row
            assert isinstance(row["learner_count"], int)

    def test_cohort_stats_no_filter(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/reports/cohort-stats")
        assert r.status_code == 200
        d = r.json()
        for k in ("learners", "enrollments", "completions", "completion_rate",
                  "avg_exam_score", "certificates_issued", "badges_earned"):
            assert k in d, f"missing {k}"

    def test_cohort_stats_with_filter(self, admin_client):
        # Use an unlikely cohort name → expect zeros
        r = admin_client.get(f"{BASE_URL}/api/admin/reports/cohort-stats",
                             params={"cohort": "__NONEXISTENT_COHORT_XYZ__"})
        assert r.status_code == 200
        d = r.json()
        assert d["learners"] == 0
        assert d["completion_rate"] == 0


# ── Cohort propagation from invitation → user on accept ───────────────
class TestCohortPropagation:
    def test_cohort_propagates_on_accept(self, admin_client):
        cohort = f"PROP-TEST-{int(time.time())}"
        email = f"TEST_cohort_prop_{int(time.time())}@example.com"
        # Bulk-invite with cohort
        r = admin_client.post(f"{BASE_URL}/api/admin/invitations/bulk", json={
            "invitations": [{"email": email, "role": "LEARNER"}],
            "cohort": cohort,
        })
        assert r.status_code == 200, r.text
        assert r.json()["queued"] == 1

        # Read token from DB
        time.sleep(0.2)
        con = sqlite3.connect(SQLITE_PATH)
        try:
            row = con.execute("SELECT token, cohort FROM invitations WHERE LOWER(email)=LOWER(?) ORDER BY id DESC LIMIT 1",
                              (email,)).fetchone()
            assert row, f"invitation row not found for {email}"
            token, inv_cohort = row
            assert inv_cohort == cohort, f"invitation cohort not stored: {inv_cohort}"
        finally:
            con.close()

        # Lookup public invitation
        r = requests.get(f"{BASE_URL}/api/invitations/{token}", timeout=10)
        assert r.status_code == 200, r.text

        # Accept invitation
        r = requests.post(f"{BASE_URL}/api/invitations/{token}/accept",
                          json={"password": "TestPass!123"}, timeout=15)
        assert r.status_code == 200, r.text
        user = r.json()["user"]
        assert user["email"].lower() == email.lower()

        # Confirm user.cohort persisted (read DB directly — not in API response)
        con = sqlite3.connect(SQLITE_PATH)
        try:
            urow = con.execute("SELECT cohort FROM users WHERE LOWER(email)=LOWER(?)", (email,)).fetchone()
            assert urow and urow[0] == cohort, f"user.cohort not propagated: {urow}"
        finally:
            con.close()


# ── PDF transcript ────────────────────────────────────────────────────
class TestTranscript:
    def test_anonymous_unauthorized(self):
        r = requests.get(f"{BASE_URL}/api/certificates/transcript", timeout=15)
        assert r.status_code in (401, 403), r.status_code

    def test_learner_can_download_pdf(self, learner_client):
        r = learner_client.get(f"{BASE_URL}/api/certificates/transcript", timeout=20)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        # PDF magic header
        assert r.content[:4] == b"%PDF", r.content[:20]
        assert len(r.content) > 1000, f"PDF too small: {len(r.content)}"

    def test_admin_can_download_pdf(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/certificates/transcript", timeout=20)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
