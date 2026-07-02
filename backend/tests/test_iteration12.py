"""Iteration 12 backend tests — Cohort webhook test ping endpoint.

Covers:
  - 422 on malformed URL (no http/https prefix)
  - non-admin (LEARNER) gets 403
  - happy path: provider auto-detected (discord/slack/generic)
  - failed ping (unreachable host) returns ok=False without 5xx
  - audit row COHORT_WEBHOOK_TESTED written
"""
from __future__ import annotations

import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    time.sleep(1.5)
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def learner_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    time.sleep(1.5)
    r = s.post(f"{BASE_URL}/api/auth/login", json=LEARNER)
    assert r.status_code == 200, f"learner login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


class TestWebhookTestEndpoint:
    def test_rejects_non_http_url(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                              json={"webhook_url": "javascript:alert(1)"})
        assert r.status_code == 422, r.text

    def test_rejects_empty_url(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                              json={"webhook_url": ""})
        # 422 from min_length=8 OR 422 from prefix check — both acceptable
        assert r.status_code == 422

    def test_learner_forbidden(self, learner_client):
        r = learner_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                                json={"webhook_url": "https://hooks.slack.com/services/T000/B000/abc"})
        assert r.status_code in (401, 403), r.text

    def test_unreachable_host_returns_ok_false(self, admin_client):
        """Webhook to a non-resolvable host should not 5xx — should return
        a structured ok=False body so the UI can show the error inline."""
        r = admin_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                              json={"webhook_url": "https://this-host-does-not-exist-9999.invalid/hook"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["status_code"] is None
        assert body["error"]  # populated
        assert body["provider"] == "generic"

    def test_discord_provider_detected(self, admin_client):
        # Use a discord-looking unreachable URL — we only care about provider tag
        r = admin_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                              json={"webhook_url": "https://discord.com/api/webhooks/nonexistent-9999/x"})
        assert r.status_code == 200, r.text
        body = r.json()
        # Either ok=True (4xx counted as not ok but reached) or ok=False (network) — both fine
        assert body["provider"] == "discord"

    def test_slack_provider_detected(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                              json={"webhook_url": "https://hooks.slack.com/services/T000/B000/invalid"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provider"] == "slack"

    def test_audit_row_written(self, admin_client):
        """A successful or failed ping should write a COHORT_WEBHOOK_TESTED audit row."""
        # Fire a ping
        admin_client.post(f"{BASE_URL}/api/organization/cohort-settings/test-webhook",
                          json={"webhook_url": "https://this-host-does-not-exist-9999.invalid/hook"})
        # Now read audit log filtered by action
        r = admin_client.get(f"{BASE_URL}/api/admin/audit-log",
                             params={"action": "COHORT_WEBHOOK_TESTED", "limit": 5})
        assert r.status_code == 200, r.text
        items = r.json().get("items") or r.json().get("data") or []
        # At least one row exists
        assert len(items) >= 1, f"expected at least one COHORT_WEBHOOK_TESTED audit row, got: {items}"
        last = items[0]
        assert last["action"] == "COHORT_WEBHOOK_TESTED"
        meta = last.get("metadata") or {}
        assert "provider" in meta
        assert "ok" in meta
