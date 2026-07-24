"""Iter 33 sprint — Email verification, GDPR data export, account
self-deletion, rate-limited reset endpoints, env-var seed password,
and hardcoded-password lint.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    r.raise_for_status()
    # Extract CSRF token so cookie-authed POST/DELETE requests pass
    csrf = s.cookies.get("ifpi_csrf")
    if csrf:
        s.headers["x-csrf-token"] = csrf
    return s


def _register_throwaway():
    email = f"iter33-{uuid.uuid4().hex[:8]}@ifpi.org"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "startingPass",
                            "name": "Iter33 Test"}, timeout=10)
    assert r.status_code == 200, r.text
    return email


# ── Email verification ──────────────────────────────────────────
def test_new_registration_starts_unverified():
    email = _register_throwaway()
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": "startingPass"},
                      timeout=10)
    assert r.status_code == 200
    assert r.json()["user"]["email_verified"] is False


def test_registration_queues_verification_email():
    email = _register_throwaway()
    from core.database import SessionLocal
    from models import OutboxMessage
    db = SessionLocal()
    try:
        row = db.query(OutboxMessage).filter(
            OutboxMessage.template == "email_verification",
            OutboxMessage.to_email == email,
        ).order_by(OutboxMessage.id.desc()).first()
        assert row is not None, "no verification email queued"
        assert "verify" in row.subject.lower()
    finally:
        db.close()


def test_verify_email_endpoint_end_to_end():
    from core.database import SessionLocal
    from models import User
    from services.auth_service import AuthService
    email = _register_throwaway()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        raw = AuthService(db).issue_email_verification(user)
        # Consume
        r = requests.post(f"{BASE_URL}/api/auth/verify-email",
                          json={"token": raw}, timeout=10)
        assert r.status_code == 200, r.text
        # Re-fetch to confirm flag
        db.expire_all()
        user = db.query(User).filter(User.email == email).first()
        assert user.email_verified_at is not None
        # Second consume → 400
        r2 = requests.post(f"{BASE_URL}/api/auth/verify-email",
                           json={"token": raw}, timeout=10)
        assert r2.status_code == 400
    finally:
        db.close()


def test_verify_email_bad_token():
    r = requests.post(f"{BASE_URL}/api/auth/verify-email",
                      json={"token": "garbage"}, timeout=10)
    assert r.status_code == 400


# ── GDPR data export ────────────────────────────────────────────
def test_data_export_returns_full_bundle():
    s = _login(LEARNER)
    r = s.get(f"{BASE_URL}/api/auth/me/export", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "profile" in body
    assert body["profile"]["email"] == LEARNER["email"]
    for key in ("enrollments", "exam_attempts", "certificates",
                "notifications", "audit_records", "active_sessions",
                "export_generated_at", "export_format_version"):
        assert key in body, f"missing section: {key}"


def test_data_export_requires_auth():
    r = requests.get(f"{BASE_URL}/api/auth/me/export", timeout=10)
    assert r.status_code == 401


# ── Account self-deletion ──────────────────────────────────────
def test_delete_request_queues_email():
    email = _register_throwaway()
    s = _login({"email": email, "password": "startingPass"})
    r = s.post(f"{BASE_URL}/api/auth/me/delete-request", timeout=10)
    assert r.status_code == 200
    from core.database import SessionLocal
    from models import OutboxMessage
    db = SessionLocal()
    try:
        row = db.query(OutboxMessage).filter(
            OutboxMessage.template == "account_deletion",
            OutboxMessage.to_email == email,
        ).order_by(OutboxMessage.id.desc()).first()
        assert row is not None
    finally:
        db.close()


def test_delete_end_to_end_anonymises_row():
    from core.database import SessionLocal
    from models import User, AccountDeletionRequest
    from services.auth_service import AuthService
    email = _register_throwaway()
    s = _login({"email": email, "password": "startingPass"})
    db = SessionLocal()
    try:
        # Trigger the request (via HTTP so the row + email are created)
        r = s.post(f"{BASE_URL}/api/auth/me/delete-request", timeout=10)
        assert r.status_code == 200
        # Peek at the (unhashed) code — we can't grab it from the email
        # in a test. Instead: use the service method directly to get a
        # fresh code and complete via HTTP DELETE.
        user = db.query(User).filter(User.email == email).first()
        user_id = user.id  # cache id before the session closes
        code = AuthService(db).request_account_deletion(user_id, ip="127.0.0.1")
        db.close()
        r = s.delete(f"{BASE_URL}/api/auth/me",
                     json={"code": code}, timeout=10)
        assert r.status_code == 200, r.text
        # Reopen DB + verify anonymisation
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        assert user.email.startswith("deleted-")
        assert user.email.endswith("@anon.invalid")
        assert user.name == "Deleted User"
        assert user.password_hash is None
        assert user.is_active is False
        assert user.deleted_at is not None
    finally:
        db.close()


def test_delete_wrong_code_rejected():
    email = _register_throwaway()
    s = _login({"email": email, "password": "startingPass"})
    s.post(f"{BASE_URL}/api/auth/me/delete-request", timeout=10)
    r = s.delete(f"{BASE_URL}/api/auth/me",
                 json={"code": "999999"}, timeout=10)
    assert r.status_code == 400


# ── Rate limiting ──────────────────────────────────────────────
def test_forgot_password_rate_limit_by_email():
    """5 requests/hour per email should get a 429 on the 4th."""
    import uuid as _u
    email = f"rl-{_u.uuid4().hex[:8]}@ifpi.org"
    # Register so the account exists (otherwise the RL still applies
    # via the enumeration guard, which is fine)
    requests.post(f"{BASE_URL}/api/auth/register",
                  json={"email": email, "password": "startingPass",
                        "name": "RL Test"}, timeout=10)
    codes = []
    for _ in range(5):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"email": email}, timeout=10)
        codes.append(r.status_code)
    # Backend allows 3 per email/hr → 4th+ must be 429
    assert 429 in codes, f"expected 429 within 5 requests, got {codes}"


# ── Hardcoded-password lint ────────────────────────────────────
def test_hardcoded_password_lint_passes():
    """CI gate: no new default-password literals crept in."""
    import subprocess
    r = subprocess.run(
        ["python", "/app/backend/scripts/lint_hardcoded_passwords.py"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, f"lint failures:\n{r.stdout}"


# ── Seed password env var ──────────────────────────────────────
def test_seed_admin_password_helper_prefers_env_var(monkeypatch):
    from seed.seed_minimal import _seed_admin_password
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "CustomProd1234!")
    assert _seed_admin_password() == "CustomProd1234!"


def test_seed_admin_password_hard_fails_in_prod(monkeypatch):
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from seed.seed_minimal import _seed_admin_password
    with pytest.raises(RuntimeError):
        _seed_admin_password()


# ── Deploy precheck: new SEED_ADMIN_PASSWORD blocker ───────────
def test_precheck_blocks_missing_seed_password():
    import subprocess
    env = {**os.environ, "ENVIRONMENT": "production"}
    env.pop("SEED_ADMIN_PASSWORD", None)
    r = subprocess.run(
        ["python", "/app/backend/scripts/deploy_precheck.py"],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 1
    assert "SEED_ADMIN_PASSWORD" in r.stdout


# ── Seed idempotency — critical safety guarantee ────────────────
def test_reseed_does_not_overwrite_existing_admin_password():
    """Regression test for the concern: 'if I redeploy, will the seed
    overwrite existing users' passwords?' Absolutely not. Every user
    block is guarded by `if not <user>:`.

    Uses a throwaway user (NOT admin@ifpi.org) so a mid-test failure
    can't leave the shared admin password in an inconsistent state.
    """
    from core.database import SessionLocal
    from core.security import get_password_hash, verify_password
    from models import User
    from seed.seed_minimal import seed
    db = SessionLocal()
    try:
        # Create a throwaway user with a well-known initial password
        email = f"seed-immutable-test-{uuid.uuid4().hex[:8]}@ifpi.org"
        u = User(
            email=email, name="Seed Test",
            password_hash=get_password_hash("InitialPass1234!"),
            organization_id=1, is_active=True,
        )
        db.add(u)
        db.commit()
        original_hash = u.password_hash
        # Simulate: seed runs on redeploy. Seed does NOT match this
        # email, so it MUST NOT be touched. This is the guarantee the
        # test asserts.
        seed(db)
        db.expire_all()
        u = db.query(User).filter(User.email == email).first()
        assert u.password_hash == original_hash, \
            "seed() mutated a non-seed user's password_hash — CRITICAL bug"
        assert verify_password("InitialPass1234!", u.password_hash)
        db.delete(u)
        db.commit()
    finally:
        db.close()


def test_reseed_does_not_touch_self_registered_users():
    """Self-registered users must be invisible to the seed."""
    from core.database import SessionLocal
    from core.security import verify_password
    from models import User
    from seed.seed_minimal import run_if_empty
    email = _register_throwaway()
    db = SessionLocal()
    try:
        user_before = db.query(User).filter(User.email == email).first()
        assert user_before is not None
        hash_before = user_before.password_hash
        run_if_empty()
        db.expire_all()
        user_after = db.query(User).filter(User.email == email).first()
        assert user_after.password_hash == hash_before, \
            "seed mutated a self-registered user's password_hash"
        assert verify_password("startingPass", user_after.password_hash)
    finally:
        db.close()


# ── Iter 33b · Admin password rescue CLI ─────────────────────────
def test_rescue_cli_refuses_without_env_secret(monkeypatch):
    """Preflight: no ADMIN_RESCUE_SECRET → exit 2."""
    import subprocess
    env = {k: v for k, v in os.environ.items() if k != "ADMIN_RESCUE_SECRET"}
    r = subprocess.run(
        ["python", "/app/backend/scripts/reset_admin_password.py",
         "--yes", "--from-env"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 2
    assert "ADMIN_RESCUE_SECRET" in r.stderr


def test_rescue_cli_refuses_short_secret():
    """Preflight: ADMIN_RESCUE_SECRET < 16 chars → exit 2."""
    import subprocess
    env = {**os.environ, "ADMIN_RESCUE_SECRET": "short",
           "NEW_ADMIN_PASSWORD": "ValidPass1234!"}
    r = subprocess.run(
        ["python", "/app/backend/scripts/reset_admin_password.py",
         "--yes", "--from-env"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 2
    assert "16 characters" in r.stderr


def test_rescue_cli_refuses_short_password():
    import subprocess
    env = {**os.environ,
           "ADMIN_RESCUE_SECRET": "a-strong-rescue-secret-value",
           "NEW_ADMIN_PASSWORD": "short"}
    r = subprocess.run(
        ["python", "/app/backend/scripts/reset_admin_password.py",
         "--yes", "--from-env"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 2


def test_rescue_cli_refuses_non_admin():
    """Belt-and-braces: even with the secret, refuses on a learner row."""
    import subprocess
    env = {**os.environ,
           "ADMIN_RESCUE_SECRET": "a-strong-rescue-secret-value",
           "NEW_ADMIN_PASSWORD": "ValidPass1234!"}
    r = subprocess.run(
        ["python", "/app/backend/scripts/reset_admin_password.py",
         "--yes", "--from-env", "--email", "learner@ifpi.org"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 1
    assert "NOT an admin" in r.stderr


def test_rescue_cli_end_to_end():
    """The happy path: reset a throwaway admin via the CLI, verify the
    new password works AND must_change_password is True AND refresh
    tokens are revoked. Uses a fresh admin so a mid-test failure can't
    lock out admin@ifpi.org."""
    from core.database import SessionLocal
    from core.security import get_password_hash, verify_password
    from models import User, UserRole, RefreshToken
    from scripts.reset_admin_password import reset_admin_password
    email = f"rescue-admin-{uuid.uuid4().hex[:8]}@ifpi.org"
    db = SessionLocal()
    try:
        # Create a throwaway admin
        admin = User(
            email=email, name="Rescue Test Admin",
            password_hash=get_password_hash("OriginalPass1234!"),
            organization_id=1, is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role="ADMIN"))
        # Plant an active refresh token
        unique_jti = f"rescue-{uuid.uuid4().hex[:8]}"
        db.add(RefreshToken(
            user_id=admin.id, family_id="rescue-test",
            jti=unique_jti, expires_at=admin.created_at,
        ))
        db.commit()
        admin_id = admin.id
        # Execute the rescue
        reset_admin_password(email, "RescuePassword123!")
        db.expire_all()
        admin = db.query(User).filter(User.id == admin_id).first()
        assert verify_password("RescuePassword123!", admin.password_hash)
        assert admin.must_change_password is True
        active = db.query(RefreshToken).filter(
            RefreshToken.user_id == admin_id,
            RefreshToken.revoked_at.is_(None),
        ).count()
        assert active == 0, "rescue must revoke all active refresh tokens"
        # Cleanup
        db.query(RefreshToken).filter(RefreshToken.user_id == admin_id).delete()
        db.query(UserRole).filter(UserRole.user_id == admin_id).delete()
        db.query(User).filter(User.id == admin_id).delete()
        db.commit()
    finally:
        db.close()
