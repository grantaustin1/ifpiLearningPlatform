"""Iteration 14 backend tests — ERP360 SSO drop-in.

Covers:
  - GET /api/auth/sso-status returns enabled flag
  - POST /api/auth/sso-exchange happy path (mint HS256 token, exchange, login)
  - Bad signature → 401
  - Wrong issuer → 401
  - Missing jti → 401
  - Replay (same jti twice) → 401
  - Expired token → 401
  - JIT provisioning creates user + roles correctly mapped (TRAINER→INSTRUCTOR)
  - Idempotent: second exchange for same erp_user_id reuses the user
  - SSO_LOGIN_SUCCESS / SSO_USER_PROVISIONED audit rows are written

We temporarily flip SSO_ENABLED/ERP360_SSO_SHARED_SECRET in /app/backend/.env
and restart the backend for the test module, then restore. The `.env` file
content is preserved bit-for-bit.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
import requests
import pytest

from jose import jwt as _jwt

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
SHARED_SECRET = "test-erp360-sso-secret-iter14-only"
ENV_PATH = "/app/backend/.env"


def _restart_backend_and_wait():
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True,
                   capture_output=True, timeout=30)
    # Poll readiness — wait up to 15s for /api/auth/sso-status to respond
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/auth/sso-status", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)


@pytest.fixture(scope="module", autouse=True)
def enable_sso():
    """Flip SSO on in .env, restart backend, then restore on teardown."""
    with open(ENV_PATH) as f:
        original = f.read()
    patched = re.sub(r"^SSO_ENABLED=.*$", "SSO_ENABLED=true",
                     original, flags=re.MULTILINE)
    patched = re.sub(r"^ERP360_SSO_SHARED_SECRET=.*$",
                     f"ERP360_SSO_SHARED_SECRET={SHARED_SECRET}",
                     patched, flags=re.MULTILINE)
    assert patched != original, "Failed to patch .env — keys not found"
    with open(ENV_PATH, "w") as f:
        f.write(patched)
    _restart_backend_and_wait()
    try:
        yield
    finally:
        with open(ENV_PATH, "w") as f:
            f.write(original)
        _restart_backend_and_wait()


def _mint_token(*, sub="9001", email="alice.trainer@erp360.test", name="Alice Trainer",
                roles=None, iat=None, exp=None, iss="erp360", aud="ifpi-lms",
                jti=None, secret=SHARED_SECRET) -> str:
    now = int(time.time())
    payload = {
        "iss": iss, "aud": aud, "sub": sub, "email": email, "name": name,
        "iat": iat if iat is not None else now,
        "exp": exp if exp is not None else (now + 60),
        "jti": jti if jti is not None else f"jti-{uuid.uuid4().hex}",
        "roles": roles or ["TRAINER"],
    }
    return _jwt.encode(payload, secret, algorithm="HS256")


class TestSSOStatus:
    def test_enabled_after_patch(self):
        r = requests.get(f"{BASE_URL}/api/auth/sso-status", timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is True


class TestSSOExchange:
    def test_happy_path_new_user_jit_provisioned(self):
        token = _mint_token(sub="9001", email="alice.trainer@erp360.test",
                            name="Alice Trainer", roles=["TRAINER"])
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["email"] == "alice.trainer@erp360.test"
        # TRAINER → INSTRUCTOR per role map
        assert "INSTRUCTOR" in body["user"]["roles"]
        # Verify the returned access_token works against /me
        access = body.get("access_token")
        assert access
        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {access}"}, timeout=10)
        assert me.status_code == 200
        assert me.json()["email"] == "alice.trainer@erp360.test"

    def test_idempotent_second_exchange_reuses_user(self):
        # Same sub, fresh jti each time
        t1 = _mint_token(sub="9002", email="bob.manager@erp360.test",
                         name="Bob", roles=["MANAGER"])
        r1 = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                           json={"erp_token": t1}, timeout=10)
        assert r1.status_code == 200, r1.text
        uid1 = r1.json()["user"]["id"]
        t2 = _mint_token(sub="9002", email="bob.manager@erp360.test",
                         name="Bob", roles=["MANAGER"])
        r2 = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                           json={"erp_token": t2}, timeout=10)
        assert r2.status_code == 200, r2.text
        uid2 = r2.json()["user"]["id"]
        assert uid1 == uid2
        # MANAGER → ADMIN per role map
        assert "ADMIN" in r2.json()["user"]["roles"]

    def test_unknown_role_falls_back_to_learner(self):
        token = _mint_token(sub="9003", email="carol.intern@erp360.test",
                            name="Carol Intern", roles=["UNKNOWN_ROLE_XYZ"])
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 200, r.text
        assert "LEARNER" in r.json()["user"]["roles"]


class TestSSOSecurityHardening:
    def test_bad_signature(self):
        token = _mint_token(sub="9101", email="evil@erp360.test",
                            secret="WRONG-SECRET-NOT-IFPI")
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 401, r.text

    def test_wrong_issuer(self):
        token = _mint_token(sub="9102", email="x@erp360.test",
                            iss="evil-issuer")
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 401
        assert "issuer" in r.json().get("detail", "").lower()

    def test_wrong_audience(self):
        token = _mint_token(sub="9103", email="x@erp360.test",
                            aud="some-other-app")
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 401

    def test_expired_token(self):
        # exp 1 minute in the past
        past = int(time.time()) - 120
        token = _mint_token(sub="9104", email="x@erp360.test",
                            iat=past - 60, exp=past)
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 401

    def test_iat_too_old(self):
        # iat way in the past but exp in the future (synthetic — should reject)
        now = int(time.time())
        token = _mint_token(sub="9105", email="x@erp360.test",
                            iat=now - 3600, exp=now + 3600)
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 401
        assert "too old" in r.json().get("detail", "").lower()

    def test_missing_jti(self):
        # Manually mint a token without jti
        now = int(time.time())
        payload = {"iss": "erp360", "aud": "ifpi-lms", "sub": "9106",
                   "email": "x@erp360.test", "iat": now, "exp": now + 60,
                   "roles": ["TRAINER"]}
        token = _jwt.encode(payload, SHARED_SECRET, algorithm="HS256")
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": token}, timeout=10)
        assert r.status_code == 401
        assert "jti" in r.json().get("detail", "").lower()

    def test_replay_same_jti_twice(self):
        jti = f"replay-{uuid.uuid4().hex}"
        token = _mint_token(sub="9107", email="replay@erp360.test", jti=jti)
        r1 = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                           json={"erp_token": token}, timeout=10)
        assert r1.status_code == 200, r1.text
        # Same token (same jti) again → must be rejected
        r2 = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                           json={"erp_token": token}, timeout=10)
        assert r2.status_code == 401
        assert "replay" in r2.json().get("detail", "").lower()


class TestSSOAudit:
    def test_audit_rows_written(self):
        # Use admin creds to read audit log
        token_admin = requests.post(f"{BASE_URL}/api/auth/login",
                                    json={"email": "admin@ifpi.org",
                                          "password": "admin123"},
                                    timeout=10).json()["access_token"]
        # Fire a fresh SSO login to generate audit rows
        sso_tok = _mint_token(sub="9201", email="audit-test@erp360.test",
                              roles=["MANAGER"])
        requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                      json={"erp_token": sso_tok}, timeout=10)
        # Login audit
        r = requests.get(f"{BASE_URL}/api/admin/audit-log",
                         params={"action": "SSO_LOGIN_SUCCESS", "limit": 5},
                         headers={"Authorization": f"Bearer {token_admin}"}, timeout=10)
        assert r.status_code == 200
        items = r.json().get("items") or []
        assert len(items) >= 1
        # Provisioning audit
        r2 = requests.get(f"{BASE_URL}/api/admin/audit-log",
                          params={"action": "SSO_USER_PROVISIONED", "limit": 5},
                          headers={"Authorization": f"Bearer {token_admin}"}, timeout=10)
        assert r2.status_code == 200
        items2 = r2.json().get("items") or []
        assert len(items2) >= 1
