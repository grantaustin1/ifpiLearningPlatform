"""Load-test scenarios for IFPI's cross-app integration surface (Iter 37).

Runs three concurrent user classes:
  - `WebhookUser`   — hammers `POST /api/erp360/webhooks/user` with
    signed `role_changed` events. Simulates ERP360 firing a burst of
    admin role updates.
  - `SsoUser`       — hammers `POST /api/auth/sso-exchange` (JSON
    binding) with freshly-minted valid tokens. Simulates a login
    stampede after a global secret rotation.
  - `EnrollmentUser` — logs in once, then bounces enrollment reads +
    writes. Simulates learner traffic after a course launch email.

Usage:
    cd /app/backend
    locust -f loadtests/locustfile.py --host http://localhost:8001

Web UI at http://localhost:8089 — set number of users and spawn rate,
watch the response-time distribution. Two failure points to look for:

    1. p95 response time on any endpoint > 5s → API Gateway 504 risk.
    2. Any 500s in the DB write paths → deadlock/lock-timeout risk.

The Iter 37 hardening (rate limiter, advisory lock, retry-on-deadlock,
background audit) is aimed squarely at pushing both failure modes past
the 10× target.

Environment variables read at startup:
    ERP360_SSO_SHARED_SECRET       — same value the app uses to verify
    IFPI_WEBHOOK_OUTBOUND_SECRET   — same value the app uses to verify
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from locust import HttpUser, between, events, task

# Load the same .env the app uses so signing keys match.
load_dotenv(Path(__file__).parent.parent / ".env")

SSO_SECRET = os.environ.get("ERP360_SSO_SHARED_SECRET", "")
WEBHOOK_SECRET = os.environ.get("IFPI_WEBHOOK_OUTBOUND_SECRET", "")


# ─── Helpers ──────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _mint_sso_token(sub: int, email: str, roles: list[str]) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": "erp360",
            "aud": "ifpi-lms",
            "sub": str(sub),
            "email": email,
            "name": f"Load Test {sub}",
            "roles": roles,
            "iat": now,
            "exp": now + 60,
            "jti": uuid.uuid4().hex,
        },
        SSO_SECRET,
        algorithm="HS256",
    )


# ─── User classes ─────────────────────────────────────────────────────
class WebhookUser(HttpUser):
    """ERP360 firing role_changed events at us."""
    wait_time = between(0.05, 0.15)  # 6–20 req/s per user
    weight = 3  # heaviest write path, weight highest

    @task
    def post_role_changed(self) -> None:
        sub = 800_000 + int(uuid.uuid4().int % 100_000)
        payload = {
            "event": "role_changed",
            "event_id": uuid.uuid4().hex,
            "occurred_at": _now_iso(),
            "org_slug": None,  # falls back to default org (single-tenant preview)
            "user": {
                "sub": str(sub),
                "email": f"load-{sub}@ifpi.test",
                "name": f"Load User {sub}",
            },
            "data": {
                "old_roles": [],
                "new_roles": [
                    {"role_name": "TRAINER", "scope": "ORG", "branch_id": None},
                ],
            },
        }
        body = json.dumps(payload).encode()
        self.client.post(
            "/api/erp360/webhooks/user",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-ERP360-Signature": _sign(body),
                "X-ERP360-Event-Id": payload["event_id"],
                "X-ERP360-Timestamp": _now_iso(),
            },
            name="POST /api/erp360/webhooks/user",
        )


class SsoUser(HttpUser):
    """Fresh SSO exchange on every task. Simulates login stampede."""
    wait_time = between(0.1, 0.3)
    weight = 2

    @task
    def sso_exchange(self) -> None:
        sub = 810_000 + int(uuid.uuid4().int % 100_000)
        token = _mint_sso_token(sub, f"sso-{sub}@ifpi.test", ["TRAINER"])
        self.client.post(
            "/api/auth/sso-exchange",
            json={"token": token},
            name="POST /api/auth/sso-exchange (json)",
        )


class ReadHeavyUser(HttpUser):
    """Public health-check pressure. Non-auth GETs — smoke test that
    read paths aren't starved by write contention."""
    wait_time = between(0.05, 0.1)
    weight = 1

    @task
    def sync_status(self) -> None:
        self.client.get("/api/erp360/sync/status",
                        name="GET /api/erp360/sync/status")


# ─── Reporting hooks ──────────────────────────────────────────────────
@events.test_start.add_listener
def _on_test_start(environment, **_) -> None:
    if not SSO_SECRET or not WEBHOOK_SECRET:
        raise RuntimeError(
            "Load-test requires ERP360_SSO_SHARED_SECRET and "
            "IFPI_WEBHOOK_OUTBOUND_SECRET in backend/.env — refusing to run "
            "without them."
        )
    print(f"[locust] Starting load test against {environment.host}")


@events.test_stop.add_listener
def _on_test_stop(environment, **_) -> None:
    stats = environment.runner.stats.total
    print(f"[locust] Finished. Total requests: {stats.num_requests}, "
          f"failures: {stats.num_failures}, "
          f"p95: {stats.get_response_time_percentile(0.95):.0f}ms, "
          f"p99: {stats.get_response_time_percentile(0.99):.0f}ms")
