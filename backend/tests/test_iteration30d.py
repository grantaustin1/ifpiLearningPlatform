"""Iter 30d — Correlation-ID + exception envelope + brute-force lockout."""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests",
                allow_module_level=True)


# ── Correlation-ID ──────────────────────────────────────────────────


def test_correlation_id_echoes_incoming_header():
    r = requests.get(f"{BASE_URL}/api/health",
                     headers={"x-correlation-id": "abc-123-test"},
                     timeout=10)
    assert r.status_code == 200
    assert r.headers.get("x-correlation-id") == "abc-123-test"


def test_correlation_id_auto_generated_when_missing():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    cid = r.headers.get("x-correlation-id")
    assert cid and len(cid) >= 16, "expected auto-generated correlation id"


def test_correlation_id_truncates_pathological_input():
    long_id = "x" * 500
    r = requests.get(f"{BASE_URL}/api/health",
                     headers={"x-correlation-id": long_id},
                     timeout=10)
    assert r.headers.get("x-correlation-id", "") != long_id  # truncated
    assert len(r.headers.get("x-correlation-id", "")) <= 64


# ── Exception envelope ──────────────────────────────────────────────


def test_404_returns_envelope():
    r = requests.get(f"{BASE_URL}/api/nonexistent-route-{os.urandom(4).hex()}",
                     timeout=10)
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "NOT_FOUND"
    assert err["status"] == 404
    assert "correlation_id" in err
    assert err["correlation_id"]


def test_401_returns_envelope_with_code():
    r = requests.get(f"{BASE_URL}/api/courses",
                     headers={"Authorization": "Bearer invalid.jwt.token"},
                     timeout=10)
    assert r.status_code == 401
    body = r.json()
    assert body.get("error", {}).get("code") == "UNAUTHENTICATED"
    assert body["error"].get("correlation_id")


# ── Brute-force lockout ─────────────────────────────────────────────


def test_login_brute_force_locks_out_after_5_failures():
    email = f"bf-test-{os.urandom(4).hex()}@example.com"
    codes = []
    for _ in range(7):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": "wrong"},
                          timeout=10)
        codes.append(r.status_code)
    # First 5 are 401 (bad creds), then 429s
    assert codes[:5] == [401] * 5, f"unexpected early codes: {codes}"
    assert 429 in codes[5:], f"lockout never fired: {codes}"

    # Retry-After header on the 429 response
    lockout = next(c for c in codes[5:] if c == 429)
    assert lockout == 429


def test_login_brute_force_resets_on_successful_login():
    """A honest user with the right password after N typo streaks shouldn't
    be locked out for the next 15 min."""
    email = "learner@ifpi.org"
    # First: 3 bad attempts
    for _ in range(3):
        requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": "wrong-pw"},
                      timeout=10)
    # Now the right password — should succeed
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": "learner123"},
                      timeout=10)
    assert r.status_code == 200, r.text
    # Immediately try again with wrong password — bucket should be reset,
    # so we get 401 not 429
    r2 = requests.post(f"{BASE_URL}/api/auth/login",
                       json={"email": email, "password": "wrong"},
                       timeout=10)
    assert r2.status_code == 401, f"bucket didn't reset: {r2.status_code}"
