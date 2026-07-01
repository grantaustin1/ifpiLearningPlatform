"""Iteration 22 — AI authoring suite foundation (Iter 22a).

Coverage:
 - Schema: source_documents, source_chunks, ai_jobs, ai_usage_ledger,
   organizations.ai_monthly_budget_cents.
 - `requires_staff()` gate: staff pass, learners get HTTP 403.
 - `/api/authoring/status` returns budget + PII policy + feature flags.
 - PII redactor: catches email/phone/id, mapping is lossless.
 - `/api/authoring/redaction/preview` endpoint end-to-end.
 - Budget update flow — ADMIN can raise cap, INSTRUCTOR cannot.
 - Public branding endpoint (`/api/branding/public`) — no auth required.
"""
from __future__ import annotations

import os
import sqlite3

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(**ADMIN)


@pytest.fixture(scope="module")
def learner():
    return _login(**LEARNER)


# ── Schema ────────────────────────────────────────────────────────────
def test_ai_infra_tables_exist():
    conn = sqlite3.connect("/app/backend/ifpi_lms.db")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for t in ("source_documents", "source_chunks", "ai_jobs", "ai_usage_ledger"):
        assert t in tables, f"missing {t}"


def test_organizations_has_ai_budget_column():
    conn = sqlite3.connect("/app/backend/ifpi_lms.db")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(organizations)")}
    conn.close()
    assert "ai_monthly_budget_cents" in cols


# ── requires_staff() gate ─────────────────────────────────────────────
def test_authoring_status_admin_can_access(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/status", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "user" in body
    assert "budget" in body
    assert body["budget"]["budget_cents"] == 20000    # locked default: $200
    assert body["pii_redaction"]["default_on"] is True
    assert body["pii_redaction"]["user_can_disable"] is True     # admin can toggle
    # Iter 23/24/25 flipped these on. Others still gated behind future iters.
    flags = body["feature_flags"]
    assert flags["tutor_enabled"] is True
    assert flags["flashcards_enabled"] is True
    # deep_research_enabled tracks TAVILY_API_KEY presence
    assert isinstance(flags["deep_research_enabled"], bool)
    # All feature flags are ON now (Iter 22 through 27c). This test ensures
    # we don't accidentally regress a flag; add specific False checks here
    # if a NEW gated feature is introduced in a future iteration.
    assert flags["tts_enabled"] is True
    assert flags["video_overview_enabled"] is True
    assert flags["visuals_enabled"] is True
    assert flags["pptx_export_enabled"] is True


def test_authoring_status_learner_blocked(learner):
    r = learner.get(f"{BASE_URL}/api/authoring/status", timeout=10)
    assert r.status_code == 403, r.text


def test_authoring_status_anonymous_blocked():
    r = requests.get(f"{BASE_URL}/api/authoring/status", timeout=10)
    assert r.status_code == 401


# ── PII redactor (unit + endpoint) ────────────────────────────────────
def test_pii_redactor_catches_email_phone_id():
    from services.pii_redactor import redact, unredact
    text = ("Please review the exam for jane.doe@example.com. "
            "Her mobile is +27 82 555 0100 and ID 8801015800083.")
    result = redact(text)
    assert result.redaction_applied is True
    assert "jane.doe@example.com" not in result.redacted_text
    assert "+27 82 555 0100" not in result.redacted_text
    assert "8801015800083" not in result.redacted_text
    assert "<email_1>" in result.redacted_text
    # Lossless round-trip
    assert unredact(result.redacted_text, result.mapping) == text


def test_pii_redactor_dedup_same_email():
    """The same email appearing twice must map to the same placeholder."""
    from services.pii_redactor import redact
    r = redact("email A: user@x.com and again B: user@x.com — same person.")
    assert r.counts.get("email") == 1     # one placeholder allocated
    assert r.redacted_text.count("<email_1>") == 2


def test_redaction_preview_endpoint(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/redaction/preview",
                   json={"text": "Ping test@ifpi.org tonight.",
                         "unredact_probe": True}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is True
    assert body["lossless"] is True
    assert "test@ifpi.org" not in body["redacted"]


def test_redaction_preview_blocks_learner(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/redaction/preview",
                     json={"text": "x@y.com"}, timeout=10)
    assert r.status_code == 403


# ── Budget flow ───────────────────────────────────────────────────────
def test_budget_snapshot(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/budget", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["budget_cents"] >= 20000
    assert body["spent_cents"] >= 0
    assert body["remaining_cents"] == body["budget_cents"] - body["spent_cents"]


def test_budget_update_admin_ok(admin):
    # Save current, bump, restore
    original = admin.get(f"{BASE_URL}/api/authoring/budget", timeout=10).json()["budget_cents"]
    r = admin.put(f"{BASE_URL}/api/authoring/budget",
                  json={"ai_monthly_budget_cents": 25000}, timeout=10)
    assert r.status_code == 200
    assert r.json()["budget_cents"] == 25000
    # Restore
    admin.put(f"{BASE_URL}/api/authoring/budget",
              json={"ai_monthly_budget_cents": original}, timeout=10)


def test_budget_update_learner_blocked(learner):
    r = learner.put(f"{BASE_URL}/api/authoring/budget",
                    json={"ai_monthly_budget_cents": 999999}, timeout=10)
    assert r.status_code == 403


def test_budget_gate_raises_429_when_over():
    """Direct-call the budget helper. Simulates an over-budget dispatch."""
    from fastapi import HTTPException
    from core.database import SessionLocal
    from models import AIUsageLedger, Organization
    from services import ai_budget_service

    db = SessionLocal()
    try:
        # Force a $200 (=20000c) ledger row on org 1 for this month
        org = db.query(Organization).filter(Organization.id == 1).first()
        original_budget = org.ai_monthly_budget_cents
        org.ai_monthly_budget_cents = 100
        db.commit()
        row = AIUsageLedger(
            organization_id=1, provider="claude", model="test",
            cost_cents=200, billing_month=ai_budget_service._current_billing_month(),
        )
        db.add(row); db.commit()
        try:
            ai_budget_service.check_budget(db, organization_id=1)
            assert False, "expected HTTPException 429"
        except HTTPException as e:
            assert e.status_code == 429
        # Cleanup
        db.delete(row)
        org.ai_monthly_budget_cents = original_budget
        db.commit()
    finally:
        db.close()


# ── Public branding endpoint ──────────────────────────────────────────
def test_public_branding_no_auth_required():
    """No Authorization header on purpose — the login page needs this."""
    r = requests.get(f"{BASE_URL}/api/branding/public", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "name" in body
    assert "primary_color" in body
    assert "logo_url" in body
    assert body["primary_color"].startswith("#")


def test_public_branding_slug_lookup():
    r = requests.get(f"{BASE_URL}/api/branding/public?slug=nonexistent", timeout=10)
    assert r.status_code == 200
    # Falls back to defaults
    assert r.json()["name"] == "Learning Platform"


def test_public_branding_does_not_leak_secrets():
    """The response must NOT contain SMTP config, budgets, or auth data."""
    r = requests.get(f"{BASE_URL}/api/branding/public", timeout=10).json()
    forbidden = {"smtp_host", "smtp_password_enc", "ai_monthly_budget_cents",
                 "created_at", "id"}
    leaked = forbidden.intersection(r.keys())
    assert not leaked, f"public branding leaked: {leaked}"
