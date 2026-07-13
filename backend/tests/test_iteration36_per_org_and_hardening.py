"""Iter 36 — P1 hardening regression tests.

Locks in four new invariants that must never regress:

- **§7.4 Per-org connection state**: SSO and webhooks resolve the
  target user WITHIN the org identified by the payload's `org_slug`.
  Standalone-org users must not be matched by email collision.
- **§7.2 Verified-email link**: on first SSO for a previously-native
  user, the native account must have `email_verified_at IS NOT NULL`
  to be linked; unverified natives return `409 Conflict`.
- **§6.3 Timestamp replay window**: `X-ERP360-Timestamp` outside ±5
  min returns `401`. Missing header is allowed (dedup is mandatory
  regardless). Malformed header returns `400`.
- **§6.4 SQL-backed idempotency**: duplicate `X-ERP360-Event-Id`
  returns 202 with `status: duplicate` and survives backend restarts.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8001")


# ─── Helpers ──────────────────────────────────────────────────────────
def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _iso_now(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def _webhook_post(payload: dict, *,
                  event_id: str | None = None,
                  timestamp: str | None = "__now__",
                  omit_timestamp: bool = False) -> requests.Response:
    """Sign + POST a webhook. `timestamp='__now__'` uses now; None → header not sent (unless omit_timestamp)."""
    secret = os.environ["IFPI_WEBHOOK_OUTBOUND_SECRET"]
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-ERP360-Signature": _sign(body, secret),
        "X-ERP360-Event-Id": event_id or uuid.uuid4().hex,
    }
    if not omit_timestamp:
        headers["X-ERP360-Timestamp"] = _iso_now() if timestamp == "__now__" else timestamp
    return requests.post(f"{BASE_URL}/api/erp360/webhooks/user",
                         data=body, headers=headers)


def _mint_sso_token(sub, email, roles, *,
                    org_slug: str | None = None,
                    name: str = "Test User") -> str:
    secret = os.environ["ERP360_SSO_SHARED_SECRET"]
    now = int(time.time())
    claims = {
        "iss": "erp360",
        "aud": "ifpi-lms",
        "sub": str(sub),
        "email": email,
        "name": name,
        "roles": roles,
        "iat": now,
        "exp": now + 60,
        "jti": uuid.uuid4().hex,
    }
    if org_slug is not None:
        claims["org_slug"] = org_slug
    return jwt.encode(claims, secret, algorithm="HS256")


# ─── §6.3 — Timestamp replay window ───────────────────────────────────
class TestTimestampReplayWindow:

    def test_missing_timestamp_header_still_accepted(self):
        """Header MAY be missing per spec — dedup on event_id is
        mandatory and does the safety work. This keeps legacy
        dispatchers working during the rollout."""
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(),
            "user": {"sub": "999001", "email": f"noheader-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload, omit_timestamp=True)
        assert r.status_code == 202, r.text

    def test_current_timestamp_accepted(self):
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(),
            "user": {"sub": "999002", "email": f"now-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload)
        assert r.status_code == 202, r.text

    def test_old_timestamp_rejected(self):
        """>5 min in the past → 401 replay."""
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(-600),
            "user": {"sub": "999003", "email": f"old-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload, timestamp=_iso_now(-600))
        assert r.status_code == 401, r.text
        assert "replay" in r.text.lower() or "window" in r.text.lower()

    def test_far_future_timestamp_rejected(self):
        """>5 min in the future → 401 (clock skew or replay attack)."""
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(600),
            "user": {"sub": "999004", "email": f"future-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload, timestamp=_iso_now(600))
        assert r.status_code == 401, r.text

    def test_malformed_timestamp_rejected_as_400(self):
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(),
            "user": {"sub": "999005", "email": f"bad-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload, timestamp="not-a-timestamp")
        assert r.status_code == 400, r.text
        assert "malformed" in r.text.lower() or "timestamp" in r.text.lower()

    def test_unix_epoch_timestamp_accepted(self):
        """Legacy dispatchers may send epoch seconds instead of ISO-8601."""
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(),
            "user": {"sub": "999006", "email": f"epoch-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload, timestamp=str(int(time.time())))
        assert r.status_code == 202, r.text


# ─── §6.4 — SQL-backed idempotency ────────────────────────────────────
class TestSqlIdempotency:

    def test_duplicate_event_id_returns_duplicate_status(self):
        event_id = uuid.uuid4().hex
        payload = {
            "event": "role_changed",
            "event_id": event_id,
            "occurred_at": _iso_now(),
            "user": {"sub": "999011", "email": f"dedup-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r1 = _webhook_post(payload, event_id=event_id)
        assert r1.status_code == 202
        assert r1.json()["status"] == "accepted"
        r2 = _webhook_post(payload, event_id=event_id)
        assert r2.status_code == 202
        assert r2.json()["status"] == "duplicate", r2.text
        assert r2.json()["event_id"] == event_id

    def test_idempotency_persists_across_restart(self):
        """Insert an event_id, restart the backend, replay — must still
        be seen as duplicate. Proves the store is SQL-backed, not
        in-memory."""
        import subprocess
        event_id = f"persist-{uuid.uuid4().hex}"
        payload = {
            "event": "role_changed",
            "event_id": event_id,
            "occurred_at": _iso_now(),
            "user": {"sub": "999021", "email": f"persist-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r1 = _webhook_post(payload, event_id=event_id)
        assert r1.status_code == 202
        assert r1.json()["status"] == "accepted"
        # Restart backend
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"],
                       check=True, capture_output=True)
        # Poll until it's back up
        for _ in range(30):
            time.sleep(0.5)
            try:
                if requests.get(f"{BASE_URL}/api/erp360/sync/status", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                continue
        # Replay same event_id
        r2 = _webhook_post(payload, event_id=event_id)
        assert r2.status_code == 202
        assert r2.json()["status"] == "duplicate", \
            f"§6.4 REGRESSION — idempotency did not persist across restart. Got: {r2.text}"


# ─── §7.4 — Per-org scoping ───────────────────────────────────────────
class TestPerOrgScoping:

    def test_sso_with_unknown_org_slug_returns_404(self):
        """Explicit `org_slug` in claim that doesn't match any org → 404
        (fails closed). Regression prevents cross-tenant fallback."""
        email = f"unknown-org-{uuid.uuid4().hex[:6]}@ifpi.test"
        token = _mint_sso_token(sub=999_031, email=email, roles=["VIEWER"],
                                org_slug="nonexistent-org-slug-xyz")
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"token": token})
        assert r.status_code == 404, r.text

    def test_sso_without_org_slug_uses_default(self):
        """Backwards compat — pre-§7.4 tokens without `org_slug` still
        JIT-provision into the default org."""
        email = f"noslug-{uuid.uuid4().hex[:6]}@ifpi.test"
        token = _mint_sso_token(sub=999_032, email=email, roles=["VIEWER"])
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"token": token})
        assert r.status_code == 200, r.text

    def test_webhook_scopes_to_org_slug(self):
        """Webhook for a `role_changed` on an unknown org_slug should
        404 rather than silently match a stranger's account by email."""
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _iso_now(),
            "org_slug": "definitely-not-a-real-org-slug",
            "user": {"sub": "999041", "email": f"crosstenant-{uuid.uuid4().hex[:6]}@ifpi.test"},
            "data": {"new_roles": []},
        }
        r = _webhook_post(payload)
        assert r.status_code == 404, r.text


# ─── §7.2 — Verified-email link on first SSO ──────────────────────────
class TestVerifiedEmailLink:

    def _create_native_user(self, email: str, verified: bool) -> int:
        """Insert a native user directly. Returns user_id."""
        from core.database import SessionLocal
        from datetime import datetime, timezone
        from models import Organization, User
        db = SessionLocal()
        try:
            org = db.query(Organization).order_by(Organization.id.asc()).first()
            u = User(
                organization_id=org.id,
                email=email,
                password_hash="not-a-real-hash",
                name="Native User",
                is_active=True,
                email_verified_at=(datetime.now(timezone.utc) if verified else None),
            )
            db.add(u)
            db.commit()
            db.refresh(u)
            return u.id
        finally:
            db.close()

    def test_verified_native_account_is_linked(self):
        email = f"verified-{uuid.uuid4().hex[:8]}@ifpi.test"
        native_id = self._create_native_user(email, verified=True)
        # SSO for the same email with a fresh sub
        token = _mint_sso_token(sub=999_051 + int(uuid.uuid4().int % 1000),
                                email=email, roles=["VIEWER"])
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"token": token})
        assert r.status_code == 200, r.text
        # Same user_id — link happened, no duplicate created
        assert r.json()["user"]["id"] == native_id

    def test_unverified_native_account_refuses_link(self):
        """§7.2 core invariant. Native account with unverified email
        must NOT be seized by a matching SSO login. 409 Conflict."""
        email = f"unverified-{uuid.uuid4().hex[:8]}@ifpi.test"
        self._create_native_user(email, verified=False)
        token = _mint_sso_token(sub=999_061 + int(uuid.uuid4().int % 1000),
                                email=email, roles=["VIEWER"])
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"token": token})
        assert r.status_code == 409, r.text
        # Message should signal the ops action
        body = r.text.lower()
        assert "unverified" in body or "not verified" in body or "verify" in body
