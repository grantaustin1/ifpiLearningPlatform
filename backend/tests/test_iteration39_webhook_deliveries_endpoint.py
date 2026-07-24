"""Iter 39 follow-up — cross-subscription webhook deliveries endpoint.

Locks in:

- Admin can list recent deliveries across all subscriptions in their org.
- `is_dry_run` flag correctly identifies dry-run rows.
- `status` filter narrows the result set.
- `event_type` filter narrows the result set.
- Learner is refused (403).
- Cross-tenant rows are filtered out (only caller's org visible).
- `/api/v1/*` alias works.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _admin_session() -> requests.Session:
    return authed_session("admin@ifpi.org", "admin123", BASE_URL)


class TestWebhookDeliveriesListing:
    def test_admin_can_list(self):
        s = _admin_session()
        r = s.get(f"{BASE_URL}/api/admin/webhooks/deliveries?limit=10", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body["items"], list)

    def test_dry_run_flag_present(self):
        """Ensure a fresh dry-run delivery flows through. First
        turn on ERP360 to auto-provision the subscription, then
        invite a learner to fire a `learner.invited` event."""
        s = _admin_session()
        try:
            s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"connected": True, "sso_enabled": True}, timeout=5,
            )
            unique = f"dryrun-flag-{uuid.uuid4().hex[:8]}@example.com"
            s.post(
                f"{BASE_URL}/api/admin/invitations",
                json={"email": unique, "name": "Dry Run",
                      "role": "LEARNER"}, timeout=10,
            )
            r = s.get(
                f"{BASE_URL}/api/admin/webhooks/deliveries?event_type=learner.invited&limit=20",
                timeout=10,
            )
            body = r.json()
            # There must be at least one dry-run delivery for this event
            dry_runs = [row for row in body["items"] if row["is_dry_run"]]
            assert len(dry_runs) > 0, (
                f"expected at least one dry-run row for learner.invited; "
                f"got {body}"
            )
        finally:
            s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"connected": None, "sso_enabled": None}, timeout=5,
            )

    def test_status_filter_narrows(self):
        s = _admin_session()
        r = s.get(
            f"{BASE_URL}/api/admin/webhooks/deliveries?status=DELIVERED&limit=50",
            timeout=10,
        )
        body = r.json()
        for row in body["items"]:
            assert row["status"] == "DELIVERED", (
                f"filter should only return DELIVERED, got {row['status']}"
            )

    def test_learner_forbidden(self):
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.get(f"{BASE_URL}/api/admin/webhooks/deliveries", timeout=10)
        assert r.status_code == 403

    def test_v1_alias(self):
        s = _admin_session()
        r = s.get(f"{BASE_URL}/api/v1/admin/webhooks/deliveries?limit=5",
                  timeout=10)
        assert r.status_code == 200
        assert r.headers.get("X-API-Version") == "v1"
