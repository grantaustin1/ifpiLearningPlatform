"""Iter 38 (Phase A) — Observability + n+1 regression locks.

Locks in three invariants:

- **Per-request query counter** works across the async→threadpool
  boundary (contextvars fail here; this is why the counter keys on
  correlation_id instead).
- **N+1 regressions** on the four hot endpoints (admin/users,
  catalog, live-sessions, leaderboard) fail the test suite — any PR
  that reintroduces lazy-load explosions must fix them before merge.
  Thresholds are set well above the current measurements (typically
  4-7 queries per endpoint post-Iter-38) to allow reasonable growth
  but catch regressions of 10× or more.
- **Request summary log line** is emitted for every request with the
  expected fields (path, status, duration_ms, queries, cid).

These tests hit real HTTP endpoints so they exercise the middleware
end-to-end.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid

import requests

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8001")
BACKEND_LOG = "/var/log/supervisor/backend.err.log"


def _tail_log_since(since_line: int) -> list[str]:
    """Return log lines added since `since_line`."""
    with open(BACKEND_LOG, "r") as f:
        lines = f.readlines()
    return lines[since_line:]


def _current_log_position() -> int:
    with open(BACKEND_LOG, "r") as f:
        return sum(1 for _ in f)


def _admin_cookies() -> requests.cookies.RequestsCookieJar:
    """Log in as admin and return a cookie jar."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return s.cookies


def _count_queries_for(path: str, cookies=None) -> int:
    """Hit `path`, wait for the log line, extract queries=N."""
    pos = _current_log_position()
    cid = uuid.uuid4().hex
    headers = {"X-Correlation-Id": cid}
    if cookies is not None:
        r = requests.get(f"{BASE_URL}{path}", headers=headers, cookies=cookies)
    else:
        r = requests.get(f"{BASE_URL}{path}", headers=headers)
    assert r.status_code < 500, f"{path} returned {r.status_code}: {r.text}"
    # Poll the log for up to 1s waiting for our cid to appear
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        for line in _tail_log_since(pos):
            if f"cid={cid}" in line and "[req]" in line:
                # Extract queries=N
                for tok in line.split():
                    if tok.startswith("queries="):
                        return int(tok.split("=", 1)[1])
        time.sleep(0.05)
    raise AssertionError(f"No [req] log line found for cid={cid} within 1s")


# ─── Per-request query counter works across threadpool ────────────────
class TestQueryCounterAcrossThreadpool:

    def test_public_endpoint_records_nonzero_queries(self):
        """`/api/catalog` hits the DB — must record >0 queries.
        A zero here means the contextvar propagation broke and
        SQLAlchemy events aren't finding the correlation_id."""
        n = _count_queries_for("/api/catalog")
        assert n > 0, f"Query counter reported 0 queries for /api/catalog — thread boundary broken?"

    def test_health_probe_records_zero_queries(self):
        """`/api/erp360/sync/status` checks env only, not DB.
        Should log queries=0 (proves we're not double-counting or
        leaking counts from other requests)."""
        n = _count_queries_for("/api/erp360/sync/status")
        assert n == 0, f"sync/status hit DB unexpectedly ({n} queries)"


# ─── N+1 regression locks ─────────────────────────────────────────────
class TestNPlusOneRegressionLocks:
    """Post-Iter-38 baseline measurements:
      - /api/admin/users:              7  queries  (was 1542)
      - /api/gamification/leaderboard: 5  queries  (was 103)
      - /api/live-sessions:            4  queries  (was 86)
      - /api/catalog:                  6  queries  (was 52)

    Thresholds set to 3× the baseline so we don't false-positive on
    small growth (a new selectinload added by a feature is fine); we
    only fail when a lazy-load explosion is reintroduced.
    """

    def test_admin_users_under_threshold(self):
        cookies = _admin_cookies()
        n = _count_queries_for("/api/admin/users", cookies=cookies)
        assert n < 30, (
            f"REGRESSION: /api/admin/users used {n} queries "
            f"(baseline 7, threshold 30). Did someone drop the "
            f"selectinload on user_roles/enrollments/certificates?"
        )

    def test_leaderboard_under_threshold(self):
        cookies = _admin_cookies()
        n = _count_queries_for("/api/gamification/leaderboard", cookies=cookies)
        assert n < 20, (
            f"REGRESSION: /api/gamification/leaderboard used {n} queries "
            f"(baseline 5, threshold 20). Check selectinload on "
            f"User.enrollments/badges."
        )

    def test_live_sessions_under_threshold(self):
        cookies = _admin_cookies()
        n = _count_queries_for("/api/live-sessions", cookies=cookies)
        assert n < 20, (
            f"REGRESSION: /api/live-sessions used {n} queries "
            f"(baseline 4, threshold 20). Check selectinload on "
            f"LiveSession.rsvps."
        )

    def test_catalog_under_threshold(self):
        n = _count_queries_for("/api/catalog")
        assert n < 20, (
            f"REGRESSION: /api/catalog used {n} queries "
            f"(baseline 6, threshold 20). Check selectinload on "
            f"Course.slides/enrollments."
        )


# ─── Request summary log line ─────────────────────────────────────────
class TestRequestSummaryLog:

    def test_line_contains_expected_fields(self):
        cid = uuid.uuid4().hex
        pos = _current_log_position()
        requests.get(f"{BASE_URL}/api/erp360/sync/status",
                     headers={"X-Correlation-Id": cid})
        # Give the middleware a moment to flush
        deadline = time.monotonic() + 1.0
        found = None
        while time.monotonic() < deadline:
            for line in _tail_log_since(pos):
                if f"cid={cid}" in line and "[req]" in line:
                    found = line
                    break
            if found:
                break
            time.sleep(0.05)
        assert found is not None, f"No [req] line for cid={cid}"
        for field in ("method=GET", "path=/api/erp360/sync/status",
                      "status=200", "duration_ms=", "queries=", f"cid={cid}"):
            assert field in found, f"Missing {field!r} in [req] line: {found}"
