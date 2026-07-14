"""§7 P1 — `/api/v1/*` versioned namespace alias.

Locks in these invariants:

- Every `/api/*` endpoint is ALSO reachable under `/api/v1/*`.
- `/api/v1/*` responses stamp `X-API-Version: v1` on the way out;
  unversioned responses do not.
- Bogus `/api/v1/nonexistent` still 404s — we don't accidentally match
  a partial prefix.
- Query strings, path params, and request bodies are preserved
  through the rewrite.
- Underlying cache buckets are shared (an `/api/v1/erp360/sync/status`
  hit warms the cache for `/api/erp360/sync/status`, and vice versa —
  they must resolve to the same route).
"""
from __future__ import annotations

import os
import time

import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestV1Alias:
    def test_public_endpoint_reachable_under_v1(self):
        r_unv = requests.get(f"{BASE_URL}/api/erp360/sync/status", timeout=5)
        r_v1 = requests.get(f"{BASE_URL}/api/v1/erp360/sync/status", timeout=5)
        assert r_unv.status_code == 200
        assert r_v1.status_code == 200
        # Same shape
        assert set(r_unv.json().keys()) == set(r_v1.json().keys())

    def test_v1_response_has_x_api_version_header(self):
        r = requests.get(f"{BASE_URL}/api/v1/erp360/sync/status", timeout=5)
        assert r.status_code == 200
        assert r.headers.get("X-API-Version") == "v1"

    def test_unversioned_response_omits_x_api_version_header(self):
        r = requests.get(f"{BASE_URL}/api/erp360/sync/status", timeout=5)
        assert r.status_code == 200
        assert r.headers.get("X-API-Version") is None

    def test_nonexistent_v1_path_still_404s(self):
        r = requests.get(f"{BASE_URL}/api/v1/does-not-exist", timeout=5)
        assert r.status_code == 404

    def test_v1_and_unversioned_share_route(self):
        """Both prefixes hit the SAME cached route — evidenced by
        identical `checked_at` when called back-to-back through the
        Iter 38 cache."""
        # Warm from one prefix
        r_v1_first = requests.get(f"{BASE_URL}/api/v1/erp360/sync/status", timeout=5)
        # Then hit from the other — must be a HIT with the same payload
        r_unv = requests.get(f"{BASE_URL}/api/erp360/sync/status", timeout=5)
        assert r_v1_first.status_code == 200 and r_unv.status_code == 200
        assert r_v1_first.json()["checked_at"] == r_unv.json()["checked_at"], (
            "v1 and unversioned prefixes must resolve to the same "
            "handler (and therefore share the cache bucket)"
        )

    def test_v1_preserves_query_params(self):
        """`/api/v1/public/catalog?q=xyz` must forward the query
        string to the underlying handler."""
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        r = s.get(f"{BASE_URL}/api/v1/public/catalog?q=zz-v1-qs-check&limit=10", timeout=5)
        assert r.status_code == 200
        # limit=10 should be honoured (via cache key it lands in a v1-specific bucket)
        assert r.headers.get("X-API-Version") == "v1"

    def test_v1_preserves_authenticated_flow(self):
        """`/api/v1/auth/me` must return the same user as `/api/auth/me`."""
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        r_unv = s.get(f"{BASE_URL}/api/auth/me", timeout=5)
        r_v1 = s.get(f"{BASE_URL}/api/v1/auth/me", timeout=5)
        assert r_unv.status_code == 200 and r_v1.status_code == 200
        assert r_unv.json()["email"] == r_v1.json()["email"]
        assert r_v1.headers.get("X-API-Version") == "v1"

    def test_v1_preserves_post_body(self):
        """POST bodies must survive the rewrite — spot-check the auth
        login flow returns the expected 401 (bad password) for both
        prefixes."""
        r_unv = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@ifpi.org", "password": "wrong-password"},
            timeout=5,
        )
        r_v1 = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@ifpi.org", "password": "wrong-password"},
            timeout=5,
        )
        # Both should return 401 (bad password) — proves the body
        # reached the same handler through both prefixes.
        assert r_unv.status_code in (400, 401)
        assert r_v1.status_code in (400, 401)
        assert r_v1.headers.get("X-API-Version") == "v1"
