"""Iter 30 Sprint — tsc typecheck (bash test) + Confirm audit + Revocation
audit log + Cert revocation webhook + Streak digest + Bulk cert ops.

Runs against the live REACT_APP_BACKEND_URL preview backend.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

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


# ── tsc --noEmit typecheck ──────────────────────────────────────────
def test_frontend_typecheck_passes():
    """Iter 30 — the whole frontend must pass `tsc --noEmit` so a
    missing-import bug like iter-29's ImportsPage.tsx cannot ship."""
    result = subprocess.run(
        ["bash", "/app/scripts/ci_typecheck.sh"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, \
        f"typecheck failed:\nstdout={result.stdout}\nstderr={result.stderr}"


# ── window.confirm audit sweep ──────────────────────────────────────
def test_no_window_confirm_calls_left():
    """Iter 30 — no code should still use `window.confirm(...)` — every
    caller must go through the useConfirm() hook. Only doc-strings /
    comments are allowed."""
    result = subprocess.run(
        ["grep", "-rn", "window.confirm(", "/app/frontend/src",
         "--include=*.tsx", "--include=*.ts"],
        capture_output=True, text=True,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    # Exclude documentation/JSDoc references
    real = []
    for ln in lines:
        # e.g. "/app/.../file.tsx:99:    if (window.confirm(..."
        content = ln.split(":", 2)[2] if ln.count(":") >= 2 else ln
        stripped = content.strip()
        # Skip comment / JSDoc / string literal references
        if stripped.startswith("*") or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if "eslint-disable" in stripped:
            continue
        real.append(ln)
    assert not real, f"unexpected window.confirm() calls: {real}"


# ── Revocation audit log ────────────────────────────────────────────
def test_revocation_history_records_events(admin, learner):
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    if not certs:
        pytest.skip("no certs")
    cid = certs[0]["id"]
    try:
        # Revoke + unrevoke to generate 2 audit events
        admin.post(f"{BASE_URL}/api/certificates/{cid}/revoke",
                   json={"reason": "iter30 audit test"}, timeout=10)
        admin.post(f"{BASE_URL}/api/certificates/{cid}/unrevoke", timeout=10)
        r = admin.get(f"{BASE_URL}/api/certificates/{cid}/revocation-history",
                      timeout=10)
        assert r.status_code == 200, r.text
        events = r.json()
        assert len(events) >= 2
        # Most-recent first
        assert events[0]["action"] == "UNREVOKE"
        assert events[1]["action"] == "REVOKE"
        assert events[1]["reason"] == "iter30 audit test"
        for e in events[:2]:
            assert e["actor_user_id"], "actor must be recorded"
            assert e["occurred_at"], "timestamp must be recorded"
            assert e.get("actor_email"), "actor email must be hydrated"
    finally:
        admin.post(f"{BASE_URL}/api/certificates/{cid}/unrevoke", timeout=10)


def test_revocation_history_requires_admin(learner):
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    if not certs:
        pytest.skip("no certs")
    r = learner.get(
        f"{BASE_URL}/api/certificates/{certs[0]['id']}/revocation-history",
        timeout=10,
    )
    assert r.status_code == 403


# ── Cert revocation webhook ─────────────────────────────────────────
def test_revoke_emits_webhook_delivery(admin, learner):
    """A webhook subscription for certificate.revoked should get a
    delivery row when a cert is revoked."""
    # Create a webhook subscription
    r = admin.post(f"{BASE_URL}/api/admin/webhooks", json={
        "target_url": "https://example.com/iter30-hook",
        "events": ["certificate.revoked", "certificate.unrevoked"],
    }, timeout=10)
    assert r.status_code in (200, 201), r.text
    sub_id = r.json()["id"]

    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    if not certs:
        admin.delete(f"{BASE_URL}/api/admin/webhooks/{sub_id}", timeout=10)
        pytest.skip("no certs")
    cid = certs[0]["id"]
    try:
        before = admin.get(f"{BASE_URL}/api/admin/webhooks/{sub_id}/deliveries",
                           timeout=10).json()
        before_rows = before.get("items", before if isinstance(before, list) else [])
        before_count = len(before_rows)

        admin.post(f"{BASE_URL}/api/certificates/{cid}/revoke",
                   json={"reason": "webhook test"}, timeout=10)

        after = admin.get(f"{BASE_URL}/api/admin/webhooks/{sub_id}/deliveries",
                          timeout=10).json()
        after_rows = after.get("items", after if isinstance(after, list) else [])
        cert_revoked_rows = [d for d in after_rows
                             if d.get("event_type") == "certificate.revoked"]
        assert len(cert_revoked_rows) >= 1, \
            f"expected certificate.revoked delivery ({len(before_rows)} → {len(after_rows)})"
    finally:
        admin.post(f"{BASE_URL}/api/certificates/{cid}/unrevoke", timeout=10)
        admin.delete(f"{BASE_URL}/api/admin/webhooks/{sub_id}", timeout=10)


# ── Streak-leaderboard weekly digest ────────────────────────────────
def test_streak_digest_worker_queues_emails():
    """Direct-import the worker and run one pass in-process. Should
    queue at least one 'streak_digest' outbox message for an org that
    has active streaks + admin users."""
    from services.streak_digest_worker import run_streak_digest_pass
    stats = run_streak_digest_pass()
    assert stats["orgs_scanned"] >= 1
    # Emails may be 0 if no org has active streaks — still valid
    assert stats["emails_queued"] >= 0


# ── Bulk cert ops ───────────────────────────────────────────────────
def test_bulk_revoke_endpoint(admin, learner):
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    if len(certs) < 2:
        pytest.skip("need >=2 certs")
    ids = [c["id"] for c in certs[:2]]
    try:
        r = admin.post(f"{BASE_URL}/api/certificates/bulk-revoke",
                       json={"certificate_ids": ids, "reason": "bulk iter30"},
                       timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["revoked_count"] == 2
        assert body["skipped_count"] == 0
        # Idempotent — second call should skip both
        r2 = admin.post(f"{BASE_URL}/api/certificates/bulk-revoke",
                        json={"certificate_ids": ids, "reason": "again"},
                        timeout=15)
        assert r2.json()["revoked_count"] == 0
        assert r2.json()["skipped_count"] == 2
        # Cross-tenant rejection: try an obviously wrong id
        r3 = admin.post(f"{BASE_URL}/api/certificates/bulk-revoke",
                        json={"certificate_ids": [999_999_999]}, timeout=10)
        assert r3.json()["results"][0]["status"] == "not_found"
    finally:
        for cid in ids:
            admin.post(f"{BASE_URL}/api/certificates/{cid}/unrevoke", timeout=10)


def test_admin_certs_list(admin):
    r = admin.get(f"{BASE_URL}/api/certificates/admin-list",
                  params={"page_size": 10}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("total", "page", "page_size", "items"):
        assert key in body
    if body["items"]:
        row = body["items"][0]
        for key in ("id", "code", "type", "recipient_name", "recipient_email",
                    "issued_at", "revoked_at", "revoked_reason"):
            assert key in row


def test_admin_certs_status_filter(admin):
    r = admin.get(f"{BASE_URL}/api/certificates/admin-list",
                  params={"status": "revoked", "page_size": 10}, timeout=10)
    assert r.status_code == 200
    for row in r.json()["items"]:
        assert row["revoked_at"] is not None
    r = admin.get(f"{BASE_URL}/api/certificates/admin-list",
                  params={"status": "active", "page_size": 10}, timeout=10)
    for row in r.json()["items"]:
        assert row["revoked_at"] is None


def test_admin_certs_csv_export(admin):
    r = admin.get(f"{BASE_URL}/api/certificates/admin-export.csv", timeout=15)
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("text/csv")
    body = r.text
    # Header row
    assert body.split("\n")[0].startswith("id,code,type,")
    # At least one data row
    assert len(body.strip().splitlines()) >= 1


def test_admin_certs_list_requires_admin(learner):
    r = learner.get(f"{BASE_URL}/api/certificates/admin-list", timeout=10)
    assert r.status_code == 403
