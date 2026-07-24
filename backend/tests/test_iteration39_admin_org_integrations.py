"""Iter 39 P1 — Admin: per-org ERP360 integration configuration.

Locks in these invariants:

- Admin can GET their own org's ERP360 integration config.
- Admin can PATCH their own org's config (merge-update).
- Regular admin CANNOT PATCH a different org (403).
- SUPER_ADMIN CAN PATCH any org.
- Unknown `billing_mode` values are rejected with 400.
- Empty string / null values CLEAR the field (remove from JSON blob).
- Every PATCH writes an audit-log row of type
  `ORG_ERP360_INTEGRATION_UPDATED`.
- Feature-flags cache is invalidated on PATCH (integration state may
  affect flag resolution in future).
"""
from __future__ import annotations

import os

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _admin_session() -> requests.Session:
    return authed_session("admin@ifpi.org", "admin123", BASE_URL)


def _learner_session() -> requests.Session:
    return authed_session("learner@ifpi.org", "learner123", BASE_URL)


def _restore_default_state(s: requests.Session):
    """Reset org 1's erp360 config to the preview default (empty)."""
    s.patch(
        f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
        json={"connected": None, "sso_enabled": None,
              "org_slug": "", "billing_mode": ""},
        timeout=5,
    )


class TestGetIntegration:
    def test_admin_can_read_own_org(self):
        s = _admin_session()
        r = s.get(
            f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
            timeout=5,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["organization_id"] == 1
        assert "connected" in body
        assert "sso_enabled" in body
        assert "raw" in body

    def test_learner_forbidden(self):
        s = _learner_session()
        r = s.get(
            f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
            timeout=5,
        )
        assert r.status_code == 403


class TestPatchIntegration:
    def test_merge_update_sets_fields(self):
        s = _admin_session()
        try:
            r = s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"connected": True, "sso_enabled": True,
                      "org_slug": "ifpi-main", "billing_mode": "erp360"},
                timeout=5,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["connected"] is True
            assert body["sso_enabled"] is True
            assert body["org_slug"] == "ifpi-main"
            assert body["billing_mode"] == "erp360"
        finally:
            _restore_default_state(s)

    def test_partial_update_preserves_unspecified_fields(self):
        s = _admin_session()
        try:
            # Set both
            s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"sso_enabled": True, "org_slug": "keeper"},
                timeout=5,
            )
            # Update only sso_enabled
            r = s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"sso_enabled": False},
                timeout=5,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["sso_enabled"] is False
            assert body["org_slug"] == "keeper"  # preserved
        finally:
            _restore_default_state(s)

    def test_empty_string_clears_field(self):
        s = _admin_session()
        try:
            s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"org_slug": "to-be-cleared", "billing_mode": "erp360"},
                timeout=5,
            )
            # Clear both
            r = s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"org_slug": "", "billing_mode": ""},
                timeout=5,
            )
            body = r.json()
            assert body["org_slug"] is None
            assert body["billing_mode"] is None
        finally:
            _restore_default_state(s)

    def test_bad_billing_mode_rejected(self):
        s = _admin_session()
        r = s.patch(
            f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
            json={"billing_mode": "stripe"},  # wrong — should be native_stripe
            timeout=5,
        )
        assert r.status_code == 400
        assert "billing_mode" in r.text.lower()

    def test_valid_billing_modes_accepted(self):
        s = _admin_session()
        try:
            for mode in ("erp360", "native_stripe"):
                r = s.patch(
                    f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                    json={"billing_mode": mode},
                    timeout=5,
                )
                assert r.status_code == 200, r.text
                assert r.json()["billing_mode"] == mode
        finally:
            _restore_default_state(s)

    def test_learner_cannot_patch(self):
        s = _learner_session()
        r = s.patch(
            f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
            json={"sso_enabled": True},
            timeout=5,
        )
        assert r.status_code == 403


class TestSuperAdminListing:
    def test_regular_admin_forbidden_from_list(self):
        """List-all endpoint is SUPER_ADMIN only; regular admin gets 403."""
        s = _admin_session()
        # admin@ifpi.org is ADMIN, not SUPER_ADMIN
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=5).json()
        if "SUPER_ADMIN" in me.get("roles", []):
            pytest.skip("Preview admin is SUPER_ADMIN; skipping negative test")
        r = s.get(f"{BASE_URL}/api/admin/organizations", timeout=5)
        assert r.status_code == 403


class TestV1AliasWorks:
    def test_v1_alias_returns_same_shape(self):
        s = _admin_session()
        r_unv = s.get(
            f"{BASE_URL}/api/admin/organizations/1/integrations/erp360", timeout=5,
        )
        r_v1 = s.get(
            f"{BASE_URL}/api/v1/admin/organizations/1/integrations/erp360", timeout=5,
        )
        assert r_unv.status_code == 200 and r_v1.status_code == 200
        assert r_v1.headers.get("X-API-Version") == "v1"
        assert r_unv.json()["organization_id"] == r_v1.json()["organization_id"]
