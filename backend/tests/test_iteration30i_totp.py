"""Iter 30i — TOTP-based 2FA end-to-end.

Runs against the live backend. Cleans up after itself by disabling 2FA
on the admin account at teardown so subsequent test runs aren't broken.
"""
from __future__ import annotations

import os

import pyotp
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
    # If 2FA gate is on for this account (residual state), we abort.
    assert not body.get("requires_2fa"), "test account has stray 2FA — clean state first"
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin():
    return _login("admin@ifpi.org", "admin123")


# ── Setup + verify happy path ─────────────────────────────────────────


def test_status_initially_disabled(admin):
    r = admin.get(f"{BASE_URL}/api/auth/2fa/status", timeout=10)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_setup_init_returns_secret_and_qr(admin):
    r = admin.post(f"{BASE_URL}/api/auth/2fa/setup-init", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["secret"]
    assert body["otpauth_url"].startswith("otpauth://totp/")
    assert body["qr_data_url"].startswith("data:image/png;base64,")


def test_full_enable_login_disable_cycle(admin):
    """The full lifecycle: enable → login gates on TOTP → challenge exchange → disable."""
    # Enable
    init = admin.post(f"{BASE_URL}/api/auth/2fa/setup-init", timeout=10).json()
    secret = init["secret"]
    code = pyotp.TOTP(secret).now()
    r = admin.post(f"{BASE_URL}/api/auth/2fa/setup",
                   json={"secret": secret, "code": code}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    recovery = body["recovery_codes"]
    assert len(recovery) == 10

    try:
        # Fresh login now requires 2FA
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@ifpi.org", "password": "admin123"},
                          timeout=15)
        assert r.status_code == 200
        gated = r.json()
        assert gated.get("requires_2fa") is True
        cid = gated["challenge_id"]
        assert gated["expires_in"] > 0

        # Bad code fails
        rB = requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                           json={"challenge_id": cid, "code": "000000"}, timeout=10)
        assert rB.status_code == 401

        # Good code passes
        good_code = pyotp.TOTP(secret).now()
        rG = requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                           json={"challenge_id": cid, "code": good_code}, timeout=10)
        assert rG.status_code == 200, rG.text
        assert rG.json()["access_token"]

        # Recovery code also works — need a fresh challenge
        r2 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": "admin@ifpi.org", "password": "admin123"},
                           timeout=15).json()
        cid2 = r2["challenge_id"]
        rR = requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                           json={"challenge_id": cid2, "code": recovery[0]},
                           timeout=10)
        assert rR.status_code == 200, rR.text
        # Used recovery code is invalidated — second use fails
        r3 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": "admin@ifpi.org", "password": "admin123"},
                           timeout=15).json()
        cid3 = r3["challenge_id"]
        rR2 = requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                            json={"challenge_id": cid3, "code": recovery[0]},
                            timeout=10)
        assert rR2.status_code == 401
    finally:
        # Cleanup: disable 2FA so the account is usable for other tests
        code = pyotp.TOTP(secret).now()
        rD = admin.post(f"{BASE_URL}/api/auth/2fa/disable",
                        json={"password": "admin123", "code": code}, timeout=10)
        assert rD.status_code == 200, rD.text
        assert rD.json()["enabled"] is False


def test_setup_rejects_bad_code(admin):
    init = admin.post(f"{BASE_URL}/api/auth/2fa/setup-init", timeout=10).json()
    r = admin.post(f"{BASE_URL}/api/auth/2fa/setup",
                   json={"secret": init["secret"], "code": "123456"}, timeout=10)
    assert r.status_code == 400


def test_status_survives_page_refresh(admin):
    """Status endpoint should reflect current DB state — sanity check."""
    r = admin.get(f"{BASE_URL}/api/auth/2fa/status", timeout=10).json()
    # After cleanup fixture, should be disabled
    assert r["enabled"] is False


def test_challenge_expired_returns_401():
    """Invalid/unknown challenge_id → 401 (opaque, no user leakage)."""
    r = requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                      json={"challenge_id": "does-not-exist", "code": "000000"},
                      timeout=10)
    assert r.status_code == 401


def test_challenge_max_attempts_locks_out(admin):
    """After 5 failed attempts against a valid challenge_id, further
    attempts must also fail (challenge is discarded)."""
    # Enable + generate a challenge
    init = admin.post(f"{BASE_URL}/api/auth/2fa/setup-init", timeout=10).json()
    secret = init["secret"]
    code = pyotp.TOTP(secret).now()
    admin.post(f"{BASE_URL}/api/auth/2fa/setup",
               json={"secret": secret, "code": code}, timeout=10).raise_for_status()
    try:
        gated = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": "admin@ifpi.org",
                                    "password": "admin123"},
                              timeout=15).json()
        cid = gated["challenge_id"]
        for _ in range(5):
            requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                          json={"challenge_id": cid, "code": "000000"},
                          timeout=10)
        # 6th (even with a valid code) must fail
        good = pyotp.TOTP(secret).now()
        r = requests.post(f"{BASE_URL}/api/auth/2fa/challenge",
                          json={"challenge_id": cid, "code": good},
                          timeout=10)
        assert r.status_code == 401
    finally:
        # Cleanup
        code = pyotp.TOTP(secret).now()
        admin.post(f"{BASE_URL}/api/auth/2fa/disable",
                   json={"password": "admin123", "code": code}, timeout=10)
