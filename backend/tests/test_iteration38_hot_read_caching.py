"""Iter 38 — Phase C follow-up: `@cached_view` + `@degrade_on_db_error`
applied to hot public reads.

Locks in these invariants (all verified via the `X-Cache: HIT/MISS`
response header the cached_view decorator emits):

1. `GET /api/erp360/sync/status` — second call is a HIT within TTL.
2. `GET /api/feature-flags` — per-org key, second call HITs.
3. `PUT /api/admin/feature-flags/{key}` — invalidates the per-org
   cache so the very next GET is a MISS again.
4. `GET /api/public/catalog` — per-org+params key, second call HITs.
5. Different query params → different cache buckets (both MISS on
   their first call).
"""
from __future__ import annotations

import os

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _admin_session() -> requests.Session:
    return authed_session("admin@ifpi.org", "admin123", BASE_URL)


def _x_cache(resp: requests.Response) -> str:
    return resp.headers.get("X-Cache", "")


class TestSyncStatusCached:
    def test_second_call_is_cache_hit(self):
        # First call may be HIT if a prior test warmed it — force MISS.
        # We can't invalidate from out-of-process, so just hit twice and
        # assert the SECOND call is HIT (proves the cache is populated).
        r1 = requests.get(f"{BASE_URL}/api/erp360/sync/status", timeout=5)
        r2 = requests.get(f"{BASE_URL}/api/erp360/sync/status", timeout=5)
        assert r1.status_code == 200 and r2.status_code == 200
        assert _x_cache(r2) == "HIT", (
            f"Second call must be a cache HIT; got X-Cache={_x_cache(r2)!r}"
        )
        # And the payload is byte-for-byte identical
        assert r1.json()["checked_at"] == r2.json()["checked_at"]


class TestFeatureFlagsCached:
    def test_second_call_is_cache_hit(self):
        s = _admin_session()
        s.get(f"{BASE_URL}/api/feature-flags", timeout=5)  # warm
        r2 = s.get(f"{BASE_URL}/api/feature-flags", timeout=5)
        assert r2.status_code == 200
        assert _x_cache(r2) == "HIT", (
            f"Second call must be a cache HIT; got X-Cache={_x_cache(r2)!r}"
        )
        assert "flags" in r2.json()

    def test_admin_toggle_invalidates_cache(self):
        s = _admin_session()
        # Warm
        s.get(f"{BASE_URL}/api/feature-flags", timeout=5)
        warmed = s.get(f"{BASE_URL}/api/feature-flags", timeout=5)
        assert _x_cache(warmed) == "HIT"

        # Flip a known flag — `marketplace` defaults to False, so we set
        # it True and restore. Using a rarely-toggled flag avoids
        # interfering with other tests.
        r = s.put(
            f"{BASE_URL}/api/admin/feature-flags/marketplace",
            json={"enabled": True, "note": "cache-invalidation-test"},
            timeout=5,
        )
        assert r.status_code == 200, r.text

        # Next GET must be a MISS (cache was invalidated)
        after = s.get(f"{BASE_URL}/api/feature-flags", timeout=5)
        assert _x_cache(after) == "MISS", (
            f"Cache must be invalidated after admin toggle; "
            f"got X-Cache={_x_cache(after)!r}"
        )
        # And the flag change is visible
        assert after.json()["flags"]["marketplace"] is True

        # Restore
        s.put(
            f"{BASE_URL}/api/admin/feature-flags/marketplace",
            json={"enabled": False, "note": "restore"},
            timeout=5,
        )


class TestPublicCatalogCached:
    def test_second_call_is_cache_hit(self):
        s = _admin_session()
        s.get(f"{BASE_URL}/api/public/catalog", timeout=5)  # warm
        r2 = s.get(f"{BASE_URL}/api/public/catalog", timeout=5)
        assert r2.status_code == 200
        assert _x_cache(r2) == "HIT", (
            f"Second catalog call must be a HIT; got X-Cache={_x_cache(r2)!r}"
        )
        assert "items" in r2.json()

    def test_different_query_uses_different_bucket(self):
        import uuid
        s = _admin_session()
        # Backend cache persists across pytest runs (30s TTL). Use a
        # fresh uuid per test invocation to guarantee cold buckets.
        tag = uuid.uuid4().hex[:8]
        q1 = f"zz-cache-{tag}-alpha"
        q2 = f"zz-cache-{tag}-beta"
        r1_a = s.get(f"{BASE_URL}/api/public/catalog?q={q1}", timeout=5)
        r1_b = s.get(f"{BASE_URL}/api/public/catalog?q={q1}", timeout=5)
        r2_a = s.get(f"{BASE_URL}/api/public/catalog?q={q2}", timeout=5)
        r2_b = s.get(f"{BASE_URL}/api/public/catalog?q={q2}", timeout=5)

        assert _x_cache(r1_a) == "MISS"
        assert _x_cache(r1_b) == "HIT"
        assert _x_cache(r2_a) == "MISS"  # separate bucket, cold
        assert _x_cache(r2_b) == "HIT"
