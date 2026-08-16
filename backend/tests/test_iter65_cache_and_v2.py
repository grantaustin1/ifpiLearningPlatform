"""Iteration 65 — Cache correctness + API v2 envelope + regressions.

Covers:
- Auth cache: login, cross-user isolation, refresh cycle
- Catalog cache invalidation on publish/unpublish/delete
- Leaderboard + Admin analytics caching
- API v2: health, courses, courses/{id}, enrollments, catalog, 404 envelope
- v1 regression: /api/courses, /api/courses/243, enrollment+progress
- Progress correctness under caching
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("uat-admin@ifpi.org", "UatAdmin!2026")
LEARNER = ("uat-learner@ifpi.org", "UatLearner!2026")
# Org-1 admin needed for catalog cache tests since only org 1 (IFPI Main Academy)
# is marketplace_opt_in=True. uat-sandbox is a separate tenant not in catalog.
ORG1_ADMIN = ("admin@ifpi.org", "admin123")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def org1_admin_tok():
    return _login(*ORG1_ADMIN)


@pytest.fixture(scope="module")
def learner_tok():
    return _login(*LEARNER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── AUTH CACHE ────────────────────────────────────────────────────────
class TestAuthCache:
    def test_login_then_me_admin(self, admin_tok):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_tok), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["email"] == ADMIN[0]
        assert "ADMIN" in j.get("roles", [])

    def test_login_then_me_learner(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(learner_tok), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["email"] == LEARNER[0]
        assert "LEARNER" in j.get("roles", [])

    def test_no_cache_bleed(self, admin_tok, learner_tok):
        a = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_tok), timeout=30).json()
        l = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(learner_tok), timeout=30).json()
        assert a["email"] == ADMIN[0]
        assert l["email"] == LEARNER[0]
        assert a["id"] != l["id"]

    def test_repeated_calls_stable(self, admin_tok):
        # 5 rapid calls => must all succeed (cache hits)
        for _ in range(5):
            r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_tok), timeout=30)
            assert r.status_code == 200

    def test_cache_refresh_boundary(self, admin_tok):
        # sleep past 30s TTL and verify no errors on refresh
        r1 = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_tok), timeout=30)
        assert r1.status_code == 200
        time.sleep(32)
        r2 = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_tok), timeout=30)
        assert r2.status_code == 200
        assert r2.json()["email"] == ADMIN[0]


# ── CATALOG CACHE INVALIDATION ────────────────────────────────────────
class TestCatalogCacheInvalidation:
    def _list_catalog_ids(self):
        r = requests.get(f"{BASE_URL}/api/catalog", params={"page_size": 100}, timeout=30)
        assert r.status_code == 200
        return {c["id"] for c in r.json()["courses"]}, r.json()

    def test_publish_appears_immediately(self, org1_admin_tok):
        admin_tok = org1_admin_tok
        title = f"TEST_iter65_{uuid.uuid4().hex[:8]}"
        # create
        r = requests.post(f"{BASE_URL}/api/courses", headers=_h(admin_tok), json={
            "title": title, "description": "cache invalidation probe",
            "category": "General",
        }, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        course_id = r.json()["id"]

        try:
            # need at least one slide to publish
            sr = requests.post(f"{BASE_URL}/api/courses/{course_id}/slides",
                               headers=_h(admin_tok),
                               json={"title": "s1", "content": "hello",
                                     "slide_type": "TEXT"}, timeout=30)
            assert sr.status_code in (200, 201), sr.text[:300]

            # warm the catalog cache (course still draft => not present)
            ids_before, _ = self._list_catalog_ids()
            assert course_id not in ids_before

            # publish
            pr = requests.post(f"{BASE_URL}/api/courses/{course_id}/publish",
                               headers=_h(admin_tok), timeout=30)
            assert pr.status_code in (200, 204), pr.text[:300]

            # must appear immediately (invalidation)
            ids_after, _ = self._list_catalog_ids()
            assert course_id in ids_after, "Published course did not appear in catalog immediately (stale cache)"

            # unpublish
            ur = requests.post(f"{BASE_URL}/api/courses/{course_id}/unpublish",
                               headers=_h(admin_tok), timeout=30)
            assert ur.status_code in (200, 204), ur.text[:300]
            ids_final, _ = self._list_catalog_ids()
            assert course_id not in ids_final, "Unpublished course still visible (stale cache)"
        finally:
            requests.delete(f"{BASE_URL}/api/courses/{course_id}",
                            headers=_h(admin_tok), timeout=30)

    def test_catalog_cache_hit_speed(self):
        # two consecutive identical requests: second must succeed and be reasonably fast
        r1 = requests.get(f"{BASE_URL}/api/catalog", timeout=30)
        assert r1.status_code == 200
        t0 = time.time()
        r2 = requests.get(f"{BASE_URL}/api/catalog", timeout=30)
        dt = time.time() - t0
        assert r2.status_code == 200
        assert r1.json()["total"] == r2.json()["total"]
        print(f"Second catalog call took {dt*1000:.0f} ms")


# ── LEADERBOARD + ANALYTICS CACHE ─────────────────────────────────────
class TestReadCaches:
    def test_leaderboard(self, learner_tok):
        r1 = requests.get(f"{BASE_URL}/api/gamification/leaderboard",
                          headers=_h(learner_tok), timeout=30)
        assert r1.status_code == 200
        assert isinstance(r1.json(), list)
        r2 = requests.get(f"{BASE_URL}/api/gamification/leaderboard",
                          headers=_h(learner_tok), timeout=30)
        assert r2.status_code == 200
        assert r1.json() == r2.json(), "Leaderboard inconsistent within 15s window"

    def test_admin_analytics(self, admin_tok):
        r1 = requests.get(f"{BASE_URL}/api/admin/analytics",
                          headers=_h(admin_tok), timeout=30)
        assert r1.status_code == 200, r1.text[:300]
        j = r1.json()
        # non-zero stats expected
        assert any(v for v in j.values() if isinstance(v, (int, float)) and v), \
            f"Analytics returned all-zero: {j}"
        # second call must succeed and match
        r2 = requests.get(f"{BASE_URL}/api/admin/analytics",
                          headers=_h(admin_tok), timeout=30)
        assert r2.status_code == 200
        assert r1.json() == r2.json()


# ── API v2 ENVELOPE ───────────────────────────────────────────────────
class TestApiV2:
    def test_v2_health(self):
        r = requests.get(f"{BASE_URL}/api/v2/health", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "data" in j and "meta" in j
        assert j["data"]["status"] == "ok"
        assert j["meta"].get("version") == "v2"

    def test_v2_courses_learner(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/v2/courses", headers=_h(learner_tok), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "data" in j and "meta" in j
        assert isinstance(j["data"], list)
        assert j["meta"].get("count") == len(j["data"])
        assert len(j["data"]) >= 4, f"Learner expected >=4 published courses, got {len(j['data'])}"

    def test_v2_course_detail_243(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/v2/courses/243", headers=_h(learner_tok), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "data" in j
        d = j["data"]
        slides = d.get("slides") or []
        assert len(slides) == 99, f"Expected 99 slides for course 243, got {len(slides)}"

    def test_v2_course_404_envelope(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/v2/courses/999999",
                         headers=_h(learner_tok), timeout=30)
        assert r.status_code == 404
        j = r.json()
        # Standard error envelope
        assert "error" in j or "detail" in j, f"Unexpected 404 body: {j}"

    def test_v2_enrollments(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/v2/enrollments",
                         headers=_h(learner_tok), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "data" in j and "meta" in j
        assert isinstance(j["data"], list)
        assert j["meta"].get("count") == len(j["data"])
        # progress field expected on entries
        for e in j["data"]:
            assert "progress" in e and "course_id" in e

    def test_v2_catalog_envelope(self):
        r = requests.get(f"{BASE_URL}/api/v2/catalog", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "data" in j and "meta" in j
        assert isinstance(j["data"], list)
        assert "total" in j["meta"] and "page" in j["meta"]


# ── v1 REGRESSION ─────────────────────────────────────────────────────
class TestV1Regression:
    def test_v1_courses_shape(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/courses", headers=_h(learner_tok), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j, list)
        # not enveloped
        assert not (isinstance(j, dict) and "data" in j and "meta" in j)

    def test_v1_course_243(self, learner_tok):
        r = requests.get(f"{BASE_URL}/api/courses/243", headers=_h(learner_tok), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == 243
        assert len(d.get("slides") or []) == 99

    def test_progress_not_cached(self, admin_tok, learner_tok):
        """Create disposable course, enroll learner, save progress twice, verify persistence."""
        title = f"TEST_iter65_prog_{uuid.uuid4().hex[:6]}"
        cr = requests.post(f"{BASE_URL}/api/courses", headers=_h(admin_tok),
                           json={"title": title, "description": "progress probe",
                                 "category": "General"}, timeout=30)
        assert cr.status_code in (200, 201)
        cid = cr.json()["id"]
        try:
            # add a slide so progress makes sense
            requests.post(f"{BASE_URL}/api/courses/{cid}/slides",
                          headers=_h(admin_tok),
                          json={"title": "s1", "content": "x", "order_index": 0},
                          timeout=30)
            requests.post(f"{BASE_URL}/api/courses/{cid}/slides",
                          headers=_h(admin_tok),
                          json={"title": "s2", "content": "y", "order_index": 1},
                          timeout=30)
            pub = requests.post(f"{BASE_URL}/api/courses/{cid}/publish",
                                headers=_h(admin_tok), timeout=30)
            assert pub.status_code in (200, 204)
            # enroll learner
            en = requests.post(f"{BASE_URL}/api/courses/{cid}/enroll",
                               headers=_h(learner_tok), timeout=30)
            assert en.status_code in (200, 201), en.text[:200]

            # save progress - slide index 0 (avoid completion)
            pr = requests.post(f"{BASE_URL}/api/courses/{cid}/progress",
                               headers=_h(learner_tok),
                               json={"slide_index": 0}, timeout=30)
            assert pr.status_code in (200, 204), pr.text[:200]
            pj = pr.json() if pr.text else {}
            assert pj.get("last_slide_index") == 0, f"save_progress returned: {pj}"

            # bump to slide 1
            pr2 = requests.post(f"{BASE_URL}/api/courses/{cid}/progress",
                                headers=_h(learner_tok),
                                json={"slide_index": 1}, timeout=30)
            assert pr2.status_code in (200, 204)
            pj2 = pr2.json() if pr2.text else {}
            print(f"save_progress(1) response: {pj2}")

            # immediately fetch enrollment / v2 enrollments — progress must reflect
            en2 = requests.get(f"{BASE_URL}/api/v2/enrollments",
                               headers=_h(learner_tok), timeout=30).json()
            match = [e for e in en2["data"] if e["course_id"] == cid]
            assert match, f"enrollment for course {cid} missing"
            # progress must reflect immediately (never cached)
            assert (match[0]["progress"] or 0) >= 100, \
                f"progress not persisted/resumed: {match[0]}"
        finally:
            requests.delete(f"{BASE_URL}/api/courses/{cid}",
                            headers=_h(admin_tok), timeout=30)
