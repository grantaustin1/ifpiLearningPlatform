"""§7.3 scoped-role-rewrite + §1.1 form-POST binding regression tests.

Locks in two invariants that must NEVER regress:

1. **IFPI-native roles survive an ERP360 `role_changed` webhook.**
   A prior version of `_replace_roles` (and `SSOService.jit_provision`)
   deleted ALL `user_roles` rows for the target user, silently
   clobbering INSTRUCTOR / cohort assignments / native admin grants.
   The fix scopes the DELETE to `source='erp360'` only. If either
   assertion in `test_role_changed_preserves_native_roles` breaks, the
   clobber-risk has resurfaced.

2. **`/api/auth/sso-exchange` accepts form-POST and returns 303.**
   This is the CORS-immune SSO binding (top-level navigation, no
   preflight). Legacy JSON path must remain untouched.

Also verifies the §6.2 role-object shape unpacking
(`{role_name, scope, branch_id}`) — v1 accept-and-ignore.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid

import jwt
import pytest
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load .env so secrets are available regardless of how pytest is invoked.
load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8001")


# ─── Helpers ──────────────────────────────────────────────────────────
def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _webhook_headers(body: bytes, event_id: str) -> dict:
    secret = os.environ.get("IFPI_WEBHOOK_OUTBOUND_SECRET", "")
    return {
        "Content-Type": "application/json",
        "X-ERP360-Signature": _sign(body, secret),
        "X-ERP360-Event-Id": event_id,
        "X-ERP360-Timestamp": str(int(time.time())),
    }


def _mint_sso_token(sub: int, email: str, roles: list, name: str = "Test User") -> str:
    """Mint an ERP360-side HS256 token that IFPI can verify."""
    secret = os.environ["ERP360_SSO_SHARED_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "iss": "erp360",
            "aud": "ifpi-lms",
            "sub": str(sub),
            "email": email,
            "name": name,
            "roles": roles,
            "iat": now,
            "exp": now + 300,
            "jti": uuid.uuid4().hex,
        },
        secret,
        algorithm="HS256",
    )


# ─── §7.3 — scoped role rewrite ───────────────────────────────────────
class TestScopedRoleRewrite:
    """§7.3 — IFPI-native roles survive ERP360 role_changed."""

    def _provision_via_sso(self, sub: int, email: str, initial_roles: list) -> int:
        """Create a user via SSO and return the user_id."""
        token = _mint_sso_token(sub, email, initial_roles)
        r = requests.post(
            f"{BASE_URL}/api/auth/sso-exchange",
            json={"token": token},
        )
        assert r.status_code == 200, r.text
        return r.json()["user"]["id"]

    def _add_native_role(self, user_id: int, role: str) -> None:
        """Directly insert a native (source='ifpi_native') role.
        Uses the DB session — no admin API needed for this regression."""
        from core.database import SessionLocal
        from models import UserRole
        db = SessionLocal()
        try:
            db.add(UserRole(user_id=user_id, role=role, source="ifpi_native"))
            db.commit()
        finally:
            db.close()

    def _get_roles(self, user_id: int) -> dict:
        """Return {role: source} for the user."""
        from core.database import SessionLocal
        from models import UserRole
        db = SessionLocal()
        try:
            rows = db.query(UserRole).filter_by(user_id=user_id).all()
            return {r.role: r.source for r in rows}
        finally:
            db.close()

    def test_role_changed_preserves_native_roles(self):
        """The core §7.3 invariant. ERP360 `role_changed` MUST NOT
        delete INSTRUCTOR (or any other native-sourced role)."""
        # Random sub so re-runs don't collide with debris users. See
        # handoff note on test state leakage.
        sub = 900_001_000 + int(uuid.uuid4().int % 1_000_000)
        email = f"scoped-test-{uuid.uuid4().hex[:8]}@ifpi.test"
        # Provision with VIEWER (maps to LEARNER, not INSTRUCTOR) so we
        # can add a native INSTRUCTOR without hitting the unique
        # (user_id, role) constraint against an erp360-sourced dup.
        user_id = self._provision_via_sso(sub, email, ["VIEWER"])
        # Add a native INSTRUCTOR grant (as if IFPI staff assigned it in-app)
        self._add_native_role(user_id, "INSTRUCTOR")

        before = self._get_roles(user_id)
        assert "INSTRUCTOR" in before, "Setup failed — native role not added"
        assert before["INSTRUCTOR"] == "ifpi_native"

        # ERP360 fires role_changed dropping TRAINER, adding LEARNER
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": "2026-07-13T15:00:00Z",
            "org_slug": "ifpi-main",
            "user": {"sub": str(sub), "email": email, "name": "Test User"},
            "data": {
                "old_roles": [{"role_name": "TRAINER", "scope": "ORG", "branch_id": None}],
                "new_roles": [{"role_name": "MANAGER", "scope": "ORG", "branch_id": None}],
            },
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{BASE_URL}/api/erp360/webhooks/user",
            data=body,
            headers=_webhook_headers(body, payload["event_id"]),
        )
        assert r.status_code == 202, r.text

        after = self._get_roles(user_id)
        # Native INSTRUCTOR MUST survive
        assert "INSTRUCTOR" in after, f"§7.3 REGRESSION — native role clobbered. Roles now: {after}"
        assert after["INSTRUCTOR"] == "ifpi_native"
        # ERP360 side reflects the new mapping (MANAGER → ADMIN per elevation)
        # and drops the previous TRAINER
        erp_roles = {role for role, src in after.items() if src == "erp360"}
        assert "TRAINER" not in erp_roles, f"Old ERP360 role not cleared: {after}"
        assert erp_roles, f"No ERP360-managed roles present after role_changed: {after}"

    def test_role_object_shape_unpacked(self):
        """§6.2 — `data.new_roles` items are objects; unpack `role_name`."""
        sub = 900_002_000 + int(uuid.uuid4().int % 1_000_000)
        email = f"shape-test-{uuid.uuid4().hex[:8]}@ifpi.test"
        user_id = self._provision_via_sso(sub, email, ["TRAINER"])

        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": "2026-07-13T15:00:00Z",
            "org_slug": "ifpi-main",
            "user": {"sub": str(sub), "email": email},
            "data": {
                "new_roles": [
                    # v1 accept-and-ignore: scope + branch_id are noise
                    {"role_name": "SALES", "scope": "BRANCH", "branch_id": 42},
                    {"role_name": "VIEWER", "scope": "ORG", "branch_id": None},
                ],
            },
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{BASE_URL}/api/erp360/webhooks/user",
            data=body,
            headers=_webhook_headers(body, payload["event_id"]),
        )
        assert r.status_code == 202, r.text
        # Should have at least one ERP360-managed role after unpacking
        after = self._get_roles(user_id)
        assert any(src == "erp360" for src in after.values()), \
            f"Role-object shape not unpacked correctly: {after}"

    def test_second_sso_login_does_not_clobber_native(self):
        """Regression on the sibling clobber-bug in SSOService.jit_provision:
        every SSO login used to full-wipe user_roles. Must now be scoped."""
        sub = 900_003_000 + int(uuid.uuid4().int % 1_000_000)
        email = f"jit-test-{uuid.uuid4().hex[:8]}@ifpi.test"
        # Use VIEWER (→ LEARNER) so a native INSTRUCTOR grant doesn't
        # collide with anything the ERP360 side owns.
        user_id = self._provision_via_sso(sub, email, ["VIEWER"])
        self._add_native_role(user_id, "INSTRUCTOR")

        # Second SSO login (as if the user clicks the tile again)
        token = _mint_sso_token(sub, email, ["MANAGER"])
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"token": token})
        assert r.status_code == 200, r.text

        after = self._get_roles(user_id)
        assert "INSTRUCTOR" in after, \
            f"jit_provision REGRESSION — native role clobbered on re-login: {after}"
        assert after["INSTRUCTOR"] == "ifpi_native"


# ─── §1.1 — form-POST binding ────────────────────────────────────────
class TestFormPostBinding:
    """§1.1 — /api/auth/sso-exchange accepts form-POST and returns 303."""

    def test_form_post_returns_303(self):
        sub = 900_101_000 + int(uuid.uuid4().int % 1_000_000)
        email = f"formpost-{uuid.uuid4().hex[:8]}@ifpi.test"
        token = _mint_sso_token(sub, email, ["TRAINER"])

        r = requests.post(
            f"{BASE_URL}/api/auth/sso-exchange",
            data={"token": token},  # form-encoded
            allow_redirects=False,
        )
        assert r.status_code == 303, f"Expected 303 See Other, got {r.status_code}: {r.text}"
        assert r.headers.get("Location") == "/dashboard"
        # Auth cookies must land on this response
        cookies = "; ".join(r.cookies.keys())
        assert any(name in cookies for name in ("ifpi_auth_token", "ifpi_refresh_token")), \
            f"No auth cookies set on 303 response. cookies={cookies!r}"

    def test_form_post_return_to_relative_path_honoured(self):
        sub = 900_102_000 + int(uuid.uuid4().int % 1_000_000)
        email = f"returnto-{uuid.uuid4().hex[:8]}@ifpi.test"
        token = _mint_sso_token(sub, email, ["TRAINER"])

        r = requests.post(
            f"{BASE_URL}/api/auth/sso-exchange",
            data={"token": token, "return_to": "/courses/42"},
            allow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers.get("Location") == "/courses/42"

    def test_form_post_return_to_open_redirect_blocked(self):
        """Attacker with a valid token cannot redirect the session to
        an external site. Absolute URLs and protocol-relative URLs
        (`//evil.example.com`) MUST fall back to /dashboard."""
        for hostile in [
            "https://evil.example.com/steal",
            "//evil.example.com/steal",
            "http://evil.example.com",
            "javascript:alert(1)",
        ]:
            # Fresh token per iteration — jti replay-protection would
            # otherwise 401 the 2nd+ attempts.
            sub = 900_103_000 + int(uuid.uuid4().int % 1_000_000)
            email = f"openredirect-{uuid.uuid4().hex[:8]}@ifpi.test"
            token = _mint_sso_token(sub, email, ["TRAINER"])
            r = requests.post(
                f"{BASE_URL}/api/auth/sso-exchange",
                data={"token": token, "return_to": hostile},
                allow_redirects=False,
            )
            assert r.status_code == 303
            assert r.headers.get("Location") == "/dashboard", \
                f"Open-redirect not blocked for {hostile!r}: got {r.headers.get('Location')!r}"

    def test_json_binding_still_returns_200_json(self):
        """Legacy JSON path must remain untouched."""
        sub = 900_104_000 + int(uuid.uuid4().int % 1_000_000)
        email = f"jsonpath-{uuid.uuid4().hex[:8]}@ifpi.test"
        token = _mint_sso_token(sub, email, ["TRAINER"])

        r = requests.post(
            f"{BASE_URL}/api/auth/sso-exchange",
            json={"token": token},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "user" in body and body["user"]["email"] == email
        assert "expires_in" in body
