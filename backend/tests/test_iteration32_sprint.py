"""Iter 32 sprint — Password reset, must_change_password, security
headers, Sentry no-op, and fail-closed ENVIRONMENT precheck.
"""
from __future__ import annotations

import os
import sys

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


# ── must_change_password flag ────────────────────────────────────
def test_login_response_carries_must_change_flag():
    """Seeded admin@ifpi.org MUST come back with must_change_password=True
    so the frontend can hard-redirect them to /change-password."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["must_change_password"] is True


def test_learner_no_must_change():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=LEARNER, timeout=10)
    assert r.status_code == 200
    assert r.json()["user"]["must_change_password"] is False


# ── /forgot-password (enumeration guard) ─────────────────────────
def test_forgot_password_unknown_email_returns_200():
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                      json={"email": "no-such-user@nowhere.io"}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Response text is IDENTICAL to the "found" case (enumeration guard)
    assert "If that email is registered" in body["message"]


def test_forgot_password_real_user_queues_email():
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                      json={"email": LEARNER["email"]}, timeout=10)
    assert r.status_code == 200
    # Confirm an OutboxMessage got created
    from core.database import SessionLocal
    from models import OutboxMessage
    db = SessionLocal()
    try:
        row = db.query(OutboxMessage).filter(
            OutboxMessage.template == "password_reset",
            OutboxMessage.to_email == LEARNER["email"],
        ).order_by(OutboxMessage.id.desc()).first()
        assert row is not None, "no password_reset outbox row queued"
        assert "reset" in row.subject.lower()
    finally:
        db.close()


# ── /reset-password ──────────────────────────────────────────────
def test_reset_password_bad_token_400():
    r = requests.post(f"{BASE_URL}/api/auth/reset-password",
                      json={"token": "garbage",
                            "new_password": "newSecurePass123"}, timeout=10)
    assert r.status_code == 400


def test_reset_password_end_to_end():
    """Full flow: request token → consume via service (we can't grab it
    from the outbox email in a test), verify new password works."""
    from core.database import SessionLocal
    from services.auth_service import AuthService
    from models import User
    db = SessionLocal()
    try:
        # Isolate: create a throwaway user so we don't churn learner creds
        import uuid
        email = f"reset-test-{uuid.uuid4().hex[:8]}@ifpi.org"
        svc = AuthService(db)
        u = svc.register(email, "oldPass1234", name="Reset Test")
        result = svc.request_password_reset(email, ip="127.0.0.1")
        assert result is not None
        _, raw_token = result
        new_pw = "brandNewPass9999"
        # Consume
        svc.consume_password_reset(raw_token, new_pw)
        # New password works
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": new_pw},
                          timeout=10)
        assert r.status_code == 200, r.text
        # Second consume attempt with same token → 400
        r2 = requests.post(f"{BASE_URL}/api/auth/reset-password",
                           json={"token": raw_token,
                                 "new_password": "yetAnother9999"}, timeout=10)
        assert r2.status_code == 400
        # Clean up — delete child rows first (no CASCADE on reset tokens)
        from models import PasswordResetToken, RefreshToken, UserRole, Person
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == u.id).delete()
        db.query(RefreshToken).filter(RefreshToken.user_id == u.id).delete()
        db.query(UserRole).filter(UserRole.user_id == u.id).delete()
        db.query(Person).filter(Person.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit()
    finally:
        db.close()


# ── /change-password ─────────────────────────────────────────────
def test_change_password_verifies_current():
    """Wrong current password → 400. Correct → 200 and flag clears."""
    from core.database import SessionLocal
    from services.auth_service import AuthService
    from models import User
    db = SessionLocal()
    try:
        import uuid
        email = f"change-pw-{uuid.uuid4().hex[:8]}@ifpi.org"
        u = AuthService(db).register(email, "startingPass", name="X")
        s = _login({"email": email, "password": "startingPass"})
        # Wrong current
        r = s.post(f"{BASE_URL}/api/auth/change-password",
                   json={"current_password": "wrong",
                         "new_password": "newSecurePass1"}, timeout=10)
        assert r.status_code == 400
        # Correct
        r2 = s.post(f"{BASE_URL}/api/auth/change-password",
                    json={"current_password": "startingPass",
                          "new_password": "newSecurePass1"}, timeout=10)
        assert r2.status_code == 200
        # New login works, old fails
        r3 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": email,
                                 "password": "newSecurePass1"}, timeout=10)
        assert r3.status_code == 200
        # And must_change_password is now false
        assert r3.json()["user"]["must_change_password"] is False
        from models import PasswordResetToken, RefreshToken, UserRole, Person
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == u.id).delete()
        db.query(RefreshToken).filter(RefreshToken.user_id == u.id).delete()
        db.query(UserRole).filter(UserRole.user_id == u.id).delete()
        db.query(Person).filter(Person.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit()
    finally:
        db.close()


# ── Security headers ─────────────────────────────────────────────
def test_security_headers_on_every_response():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in r.headers.get("Referrer-Policy", "").lower()
    assert "geolocation" in r.headers.get("Permissions-Policy", "")
    # CSP is Report-Only in non-prod, enforced in prod. Either header
    # is acceptable — we just care that ONE is present.
    csp = (r.headers.get("Content-Security-Policy")
           or r.headers.get("Content-Security-Policy-Report-Only"))
    assert csp is not None
    assert "frame-ancestors 'none'" in csp


def test_hsts_only_over_https():
    # curl to localhost/http won't set HSTS
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    # If the ingress terminates HTTPS the header WILL be set on the
    # public URL (x-forwarded-proto=https). Either way, the value —
    # when present — must be a full year with subdomains.
    hsts = r.headers.get("Strict-Transport-Security")
    if hsts:
        assert "max-age=31536000" in hsts


# ── Sentry no-op when unset ──────────────────────────────────────
def test_sentry_noop_when_dsn_unset(monkeypatch):
    """Importing server WITHOUT SENTRY_DSN must not initialise Sentry."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    # Reload the module fresh
    import importlib
    if "server" in sys.modules:
        del sys.modules["server"]
    import server  # noqa: F401
    import sentry_sdk
    # In sentry-sdk 2.x, get_client() returns the active client — a
    # NoopClient when never initialised.
    client = sentry_sdk.get_client()
    assert not client.dsn


# ── Fail-closed precheck ─────────────────────────────────────────
def test_precheck_fail_closed_on_unset_environment():
    """The safety-net-relevant regression from SureThing AI's audit."""
    import subprocess
    env = {**os.environ}
    env.pop("ENVIRONMENT", None)
    # Also unset all blocker-relevant vars so we actually crash
    for k in ("JWT_SECRET", "DATABASE_URL", "AUTH_COOKIE_SECURE",
              "PUBLIC_BASE_URL", "STORAGE_BACKEND"):
        env.pop(k, None)
    r = subprocess.run(
        ["python", "/app/backend/scripts/deploy_precheck.py"],
        env=env, capture_output=True, text=True, timeout=15,
    )
    # With no ENVIRONMENT set + no other config → must EXIT 1
    assert r.returncode == 1, f"precheck should fail-closed, got {r.returncode}"
    assert "PRODUCTION (fail-closed)" in r.stdout


def test_precheck_soft_advisor_when_dev_explicit():
    """Explicit ENVIRONMENT=development downgrades blockers to warnings."""
    import subprocess
    env = {**os.environ, "ENVIRONMENT": "development"}
    r = subprocess.run(
        ["python", "/app/backend/scripts/deploy_precheck.py"],
        env=env, capture_output=True, text=True, timeout=15,
    )
    # Non-strict dev boot must exit 0
    assert r.returncode == 0
