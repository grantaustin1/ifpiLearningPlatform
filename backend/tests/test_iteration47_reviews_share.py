"""Iter 47 — Shareable course links + course written reviews.

Tests:
  * public catalog detail returns avg_rating / rating_count
  * public catalog reviews returns visible reviews, anonymised name
  * POST rating with comment (auth + completed enrollment)
  * comment preserved when re-posting only rating
  * admin list reviews + toggle-hidden → hides from public
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

UAT_ADMIN = ("uat-admin@ifpi.org", "UatAdmin!2026")
UAT_LEARNER = ("uat-learner@ifpi.org", "UatLearner!2026")


def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-Return-Token": "true"},
        timeout=15,
    )
    r.raise_for_status()
    tok = r.json().get("access_token")
    assert tok, f"No access token for {email}"
    return tok


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(*UAT_ADMIN)


@pytest.fixture(scope="module")
def learner_token():
    return _login(*UAT_LEARNER)


@pytest.fixture(scope="module")
def ensure_market_opt_in(admin_token):
    """UAT org must be marketplace_opt_in=True so catalog endpoints return the course."""
    # Try to flip via admin org settings if endpoint exists; else assume already on.
    r = requests.get(f"{BASE_URL}/api/organizations/me", headers=_hdr(admin_token), timeout=10)
    if r.status_code == 200 and r.json().get("marketplace_opt_in") is False:
        # try patch
        requests.patch(f"{BASE_URL}/api/organizations/me",
                       json={"marketplace_opt_in": True},
                       headers=_hdr(admin_token), timeout=10)
    return True


@pytest.fixture(scope="module")
def seeded_course(admin_token, learner_token, ensure_market_opt_in):
    """Create a course, publish, enrol learner, complete, so learner can rate."""
    suffix = uuid.uuid4().hex[:6]
    title = f"TEST_Iter47_Course_{suffix}"
    r = requests.post(
        f"{BASE_URL}/api/courses",
        json={"title": title, "description": "Iter47 review-test course"},
        headers=_hdr(admin_token), timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    course_id = r.json()["id"]

    # Add a slide (some completion flows require slides)
    requests.post(
        f"{BASE_URL}/api/courses/{course_id}/slides",
        json={"title": "S1", "content_html": "<p>hi</p>", "order_index": 0},
        headers=_hdr(admin_token), timeout=10,
    )
    # Publish
    p = requests.post(f"{BASE_URL}/api/courses/{course_id}/publish",
                      headers=_hdr(admin_token), timeout=10)
    assert p.status_code in (200, 204), p.text

    # Learner enrolls + completes
    e = requests.post(f"{BASE_URL}/api/courses/{course_id}/enroll",
                      headers=_hdr(learner_token), timeout=10)
    assert e.status_code in (200, 201), e.text
    c = requests.post(f"{BASE_URL}/api/courses/{course_id}/complete",
                      headers=_hdr(learner_token), timeout=15)
    assert c.status_code in (200, 201), c.text

    yield course_id

    # Best-effort cleanup
    requests.delete(f"{BASE_URL}/api/courses/{course_id}",
                    headers=_hdr(admin_token), timeout=10)


# ─── Rating + comment upsert semantics ─────────────────────────────
class TestRatingComment:
    def test_post_rating_with_comment(self, seeded_course, learner_token):
        r = requests.post(
            f"{BASE_URL}/api/courses/{seeded_course}/rating",
            json={"rating": 5, "comment": "TEST_Iter47 amazing course"},
            headers=_hdr(learner_token), timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["my_rating"] == 5
        assert body["rating_count"] >= 1
        assert body["avg_rating"] is not None

    def test_get_rating_returns_comment(self, seeded_course, learner_token):
        r = requests.get(f"{BASE_URL}/api/courses/{seeded_course}/rating",
                         headers=_hdr(learner_token), timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j["my_rating"] == 5
        assert j["my_comment"] == "TEST_Iter47 amazing course"

    def test_repost_rating_only_preserves_comment(self, seeded_course, learner_token):
        r = requests.post(
            f"{BASE_URL}/api/courses/{seeded_course}/rating",
            json={"rating": 4},  # no comment key
            headers=_hdr(learner_token), timeout=10,
        )
        assert r.status_code == 200
        g = requests.get(f"{BASE_URL}/api/courses/{seeded_course}/rating",
                         headers=_hdr(learner_token), timeout=10).json()
        assert g["my_rating"] == 4
        assert g["my_comment"] == "TEST_Iter47 amazing course", \
            f"Comment wiped! got {g['my_comment']!r}"

    def test_rating_out_of_range_422(self, seeded_course, learner_token):
        r = requests.post(
            f"{BASE_URL}/api/courses/{seeded_course}/rating",
            json={"rating": 6},
            headers=_hdr(learner_token), timeout=10,
        )
        assert r.status_code == 422


# ─── Public catalog exposure ───────────────────────────────────────
class TestPublicCatalog:
    def test_catalog_detail_has_avg_rating(self, seeded_course):
        r = requests.get(f"{BASE_URL}/api/catalog/{seeded_course}", timeout=10)
        if r.status_code == 404:
            pytest.skip("UAT org not marketplace_opt_in — catalog hides course")
        assert r.status_code == 200
        j = r.json()
        assert "avg_rating" in j and "rating_count" in j
        assert j["rating_count"] >= 1
        assert j["avg_rating"] is not None

    def test_catalog_reviews_public_and_anonymised(self, seeded_course):
        r = requests.get(f"{BASE_URL}/api/catalog/{seeded_course}/reviews", timeout=10)
        if r.status_code == 404:
            pytest.skip("catalog hides course (org not opt-in)")
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert any(x.get("comment") == "TEST_Iter47 amazing course" for x in arr)
        for x in arr:
            # Reviewer should be short/anonymised — not full email
            assert "@" not in (x.get("reviewer") or "")

    def test_catalog_reviews_404_for_unknown(self):
        r = requests.get(f"{BASE_URL}/api/catalog/99999999/reviews", timeout=10)
        assert r.status_code == 404


# ─── Admin moderation ──────────────────────────────────────────────
class TestAdminModeration:
    def test_admin_list_reviews_includes_hidden_flag(self, seeded_course, admin_token):
        r = requests.get(f"{BASE_URL}/api/courses/{seeded_course}/reviews",
                         headers=_hdr(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        arr = r.json()
        assert len(arr) >= 1
        assert "hidden" in arr[0] and "id" in arr[0]

    def test_toggle_hidden_hides_from_public(self, seeded_course, admin_token):
        # Grab review id
        arr = requests.get(f"{BASE_URL}/api/courses/{seeded_course}/reviews",
                           headers=_hdr(admin_token), timeout=10).json()
        rid = arr[0]["id"]

        # Toggle → hidden
        t = requests.post(
            f"{BASE_URL}/api/courses/{seeded_course}/reviews/{rid}/toggle-hidden",
            headers=_hdr(admin_token), timeout=10,
        )
        assert t.status_code == 200
        assert t.json()["hidden"] is True

        # Public should now not see it
        pub = requests.get(f"{BASE_URL}/api/catalog/{seeded_course}/reviews", timeout=10)
        if pub.status_code == 200:
            assert not any(x["id"] == rid for x in pub.json()), "hidden review still public"

        # Toggle again → un-hide (restore state)
        t2 = requests.post(
            f"{BASE_URL}/api/courses/{seeded_course}/reviews/{rid}/toggle-hidden",
            headers=_hdr(admin_token), timeout=10,
        )
        assert t2.status_code == 200
        assert t2.json()["hidden"] is False

    def test_learner_cannot_list_admin_reviews(self, seeded_course, learner_token):
        r = requests.get(f"{BASE_URL}/api/courses/{seeded_course}/reviews",
                         headers=_hdr(learner_token), timeout=10)
        assert r.status_code in (401, 403)
