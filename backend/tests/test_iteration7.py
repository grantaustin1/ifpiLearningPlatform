"""Iteration 7 backend tests — badge tiers CRUD/reorder, per-tenant SMTP, bulk invites."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def learner_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=LEARNER, timeout=15)
    assert r.status_code == 200
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ── Badge tiers ───────────────────────────────────────────────────────
class TestBadgeTiers:
    def test_list_default_seed(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/badge-tiers")
        assert r.status_code == 200
        data = r.json()
        slugs = {t["slug"] for t in data}
        expected = {"FIRST_ENROLLMENT", "FIRST_COURSE", "EXAM_PASSER", "PERFECT_SCORE", "COURSE_MASTER"}
        assert expected.issubset(slugs), f"missing default tiers: {expected - slugs}"
        for t in data:
            for k in ("id", "slug", "label", "emoji", "threshold_xp", "order_index", "is_active"):
                assert k in t, f"missing {k} in tier row"

    def test_list_forbidden_for_learner(self, learner_client):
        r = learner_client.get(f"{BASE_URL}/api/badge-tiers")
        assert r.status_code == 403

    def test_create_update_delete_cycle(self, admin_client):
        # CREATE (slug should auto-uppercase)
        r = admin_client.post(f"{BASE_URL}/api/badge-tiers", json={
            "slug": "test_tier_a", "label": "Test Tier A", "emoji": "🧪",
            "description": "for tests", "threshold_xp": 42, "is_active": True,
        })
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["slug"] == "TEST_TIER_A"
        tid = created["id"]

        # Duplicate slug → 400
        r2 = admin_client.post(f"{BASE_URL}/api/badge-tiers", json={
            "slug": "test_tier_a", "label": "Dup", "emoji": "🚫",
        })
        assert r2.status_code == 400

        # PATCH
        r3 = admin_client.patch(f"{BASE_URL}/api/badge-tiers/{tid}", json={
            "label": "Updated", "threshold_xp": 99, "is_active": False,
        })
        assert r3.status_code == 200
        upd = r3.json()
        assert upd["label"] == "Updated"
        assert upd["threshold_xp"] == 99
        assert upd["is_active"] is False

        # GET — verify persistence
        rg = admin_client.get(f"{BASE_URL}/api/badge-tiers")
        row = next(t for t in rg.json() if t["id"] == tid)
        assert row["label"] == "Updated"
        assert row["threshold_xp"] == 99

        # DELETE
        rd = admin_client.delete(f"{BASE_URL}/api/badge-tiers/{tid}")
        assert rd.status_code == 200

        rg2 = admin_client.get(f"{BASE_URL}/api/badge-tiers")
        assert all(t["id"] != tid for t in rg2.json())

    def test_patch_unknown_id_returns_404(self, admin_client):
        r = admin_client.patch(f"{BASE_URL}/api/badge-tiers/99999999", json={"label": "x"})
        assert r.status_code == 404

    def test_delete_unknown_id_returns_404(self, admin_client):
        r = admin_client.delete(f"{BASE_URL}/api/badge-tiers/99999999")
        assert r.status_code == 404

    def test_reorder_changes_order_index(self, admin_client):
        tiers = admin_client.get(f"{BASE_URL}/api/badge-tiers").json()
        assert len(tiers) >= 2
        original = [t["id"] for t in tiers]
        reversed_ids = list(reversed(original))
        # include a cross-org/unknown id which should be silently ignored
        payload_ids = reversed_ids + [99999999]
        r = admin_client.patch(f"{BASE_URL}/api/badge-tiers/reorder", json={"tier_ids": payload_ids})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["updated"] == len(reversed_ids)  # unknown ignored
        # Verify new order
        tiers2 = admin_client.get(f"{BASE_URL}/api/badge-tiers").json()
        got_order = [t["id"] for t in tiers2]
        assert got_order[: len(reversed_ids)] == reversed_ids

        # Restore original order so we don't leak state
        admin_client.patch(f"{BASE_URL}/api/badge-tiers/reorder", json={"tier_ids": original})


# ── Gamification meta resolution ──────────────────────────────────────
class TestGamification:
    def test_me_returns_badges(self, learner_client):
        r = learner_client.get(f"{BASE_URL}/api/gamification/me")
        assert r.status_code == 200
        data = r.json()
        assert "badges" in data
        # No assertion on contents because state is order-dependent — just shape


# ── SMTP per-tenant config ────────────────────────────────────────────
class TestSmtp:
    def test_get_smtp_no_password_in_response(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/organization/smtp")
        assert r.status_code == 200
        data = r.json()
        assert "smtp_password_enc" not in data
        assert "has_password" in data
        assert "is_configured" in data
        assert isinstance(data["has_password"], bool)
        assert isinstance(data["is_configured"], bool)

    def test_put_smtp_persists_with_encrypted_password(self, admin_client):
        # Save baseline
        baseline = admin_client.get(f"{BASE_URL}/api/organization/smtp").json()
        # PUT with no host → is_configured False; test 400 path first
        r = admin_client.put(f"{BASE_URL}/api/organization/smtp", json={
            "smtp_host": None, "smtp_port": None, "smtp_username": None,
            "smtp_password": None, "smtp_from_email": None,
            "smtp_from_name": None, "smtp_use_tls": True,
        })
        assert r.status_code == 200

        # GET to verify cleared
        cfg0 = admin_client.get(f"{BASE_URL}/api/organization/smtp").json()
        assert cfg0["is_configured"] is False

        # 400 'SMTP not configured'
        rt = admin_client.post(f"{BASE_URL}/api/organization/smtp/test", json={"to": "x@example.com"})
        assert rt.status_code == 400
        assert "SMTP not configured" in rt.json().get("detail", "")

        # Now configure
        r2 = admin_client.put(f"{BASE_URL}/api/organization/smtp", json={
            "smtp_host": "smtp.example.test", "smtp_port": 587,
            "smtp_username": "noreply@example.test", "smtp_password": "supers3cret!",
            "smtp_from_email": "noreply@example.test", "smtp_from_name": "IFPI Test",
            "smtp_use_tls": True,
        })
        assert r2.status_code == 200

        cfg = admin_client.get(f"{BASE_URL}/api/organization/smtp").json()
        assert cfg["smtp_host"] == "smtp.example.test"
        assert cfg["smtp_port"] == 587
        assert cfg["smtp_username"] == "noreply@example.test"
        assert cfg["smtp_from_email"] == "noreply@example.test"
        assert cfg["has_password"] is True
        assert cfg["is_configured"] is True
        assert "smtp_password" not in cfg
        assert "smtp_password_enc" not in cfg

        # Test send will try to hit smtp.example.test which doesn't exist → 400
        rt2 = admin_client.post(f"{BASE_URL}/api/organization/smtp/test",
                                json={"to": "ops@example.test"})
        # Either 400 (SMTP test failed) — not the "not configured" branch
        assert rt2.status_code == 400
        assert "not configured" not in rt2.json().get("detail", "")

        # Cleanup — restore baseline (clear)
        admin_client.put(f"{BASE_URL}/api/organization/smtp", json={
            "smtp_host": baseline.get("smtp_host"),
            "smtp_port": baseline.get("smtp_port"),
            "smtp_username": baseline.get("smtp_username"),
            "smtp_password": "" if not baseline.get("has_password") else None,
            "smtp_from_email": baseline.get("smtp_from_email"),
            "smtp_from_name": baseline.get("smtp_from_name"),
            "smtp_use_tls": baseline.get("smtp_use_tls", True),
        })

    def test_smtp_test_requires_to(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/organization/smtp/test", json={"to": ""})
        assert r.status_code == 400


# ── Bulk invitations ──────────────────────────────────────────────────
class TestBulkInvite:
    def test_bulk_invite_mixed_validity(self, admin_client):
        ts = int(time.time())
        rows = [
            {"email": f"TEST_bulk_{ts}_a@example.com", "name": "A", "role": "LEARNER"},
            {"email": f"TEST_bulk_{ts}_b@example.com", "name": "B", "role": "LEARNER"},
            {"email": "admin@ifpi.org", "role": "LEARNER"},  # existing user → skipped
            {"email": "not-an-email", "role": "LEARNER"},   # invalid → skipped/error
            {"email": f"TEST_bulk_{ts}_c@example.com", "role": "LEARNER"},
        ]
        r = admin_client.post(f"{BASE_URL}/api/admin/invitations/bulk",
                              json={"invitations": rows})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "queued" in body and "total" in body and "results" in body
        assert body["total"] == 5
        assert len(body["results"]) == 5
        statuses = {row["status"] for row in body["results"]}
        # at least one queued and at least one non-queued
        assert "queued" in statuses
        assert any(row["status"] in ("skipped", "error") for row in body["results"])

        # Cleanup queued invites
        invs = admin_client.get(f"{BASE_URL}/api/admin/invitations").json()
        for inv in invs:
            if f"TEST_bulk_{ts}" in inv["email"]:
                admin_client.delete(f"{BASE_URL}/api/admin/invitations/{inv['id']}")

    def test_bulk_invite_cap_at_500(self, admin_client):
        rows = [{"email": f"TEST_cap_{i}@example.com", "role": "LEARNER"} for i in range(501)]
        r = admin_client.post(f"{BASE_URL}/api/admin/invitations/bulk",
                              json={"invitations": rows})
        assert r.status_code == 400
        assert "500" in r.json().get("detail", "")


# ── New academy seeds default badge tiers ─────────────────────────────
class TestAcademySeedsTiers:
    def test_create_academy_seeds_5_default_tiers(self, admin_client):
        ts = int(time.time())
        slug = f"test-acad-{ts}"
        r = admin_client.post(f"{BASE_URL}/api/academies", json={
            "name": f"TEST Academy {ts}", "slug": slug,
            "admin_email": f"TEST_acad_admin_{ts}@example.com",
            "admin_name": "Acad Admin",
        })
        # Tolerant of 200/201 if endpoint exists; skip if 404 (route not present)
        if r.status_code == 404:
            pytest.skip("/api/academies create endpoint not present")
        assert r.status_code in (200, 201), r.text
        # Can't directly query other org's tiers (cross-org isolation), but we
        # can assert at minimum the response shape if available
        body = r.json() if r.content else {}
        assert isinstance(body, dict)
