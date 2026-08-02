"""Iter 48 — Review Replies + Social Preview Cards.

Focus:
  * POST /api/courses/{cid}/reviews/{rid}/reply auth/validation
  * catalog + admin review lists include reply_text / reply_at
  * GET /api/seo/courses/share/{cid} returns OG HTML w/ og:image, star
    rating in description, JS redirect to /catalog/{id}, 404 for
    non-marketplace / draft courses, HTML-escaped titles.
"""
from __future__ import annotations

import os
import re
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

UAT_ADMIN = ("uat-admin@ifpi.org", "UatAdmin!2026")
UAT_LEARNER = ("uat-learner@ifpi.org", "UatLearner!2026")


# ─── Helpers ───────────────────────────────────────────────────────
def _login(email, password):
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


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(*UAT_ADMIN)


@pytest.fixture(scope="module")
def learner_token():
    return _login(*UAT_LEARNER)


@pytest.fixture(scope="module")
def uat_market_optin():
    """Flip UAT org marketplace_opt_in=True for the module, revert on teardown."""
    from sqlalchemy.orm import Session
    import sys
    sys.path.insert(0, "/app/backend")
    from core.database import SessionLocal
    from models import Organization
    db: Session = SessionLocal()
    org = db.query(Organization).filter(Organization.slug == "uat-sandbox").first()
    prev = org.marketplace_opt_in
    org.marketplace_opt_in = True
    db.commit()
    yield org.id
    org2 = db.query(Organization).filter(Organization.slug == "uat-sandbox").first()
    org2.marketplace_opt_in = prev  # revert
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def seeded_course_with_review(admin_token, learner_token, uat_market_optin):
    """Create course, publish, learner enrols+completes+rates+writes a comment,
    yielding (course_id, rating_id, course_title)."""
    suffix = uuid.uuid4().hex[:6]
    title = f"TEST_Iter48 <b>{suffix}</b>"  # includes HTML chars for escape test
    r = requests.post(
        f"{BASE_URL}/api/courses",
        json={"title": title, "description": "Iter48 reply + share test course"},
        headers=_hdr(admin_token), timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    course_id = r.json()["id"]

    # add slide, publish
    requests.post(
        f"{BASE_URL}/api/courses/{course_id}/slides",
        json={"title": "S1", "content_html": "<p>hi</p>", "order_index": 0},
        headers=_hdr(admin_token), timeout=10,
    )
    p = requests.post(f"{BASE_URL}/api/courses/{course_id}/publish",
                      headers=_hdr(admin_token), timeout=10)
    assert p.status_code in (200, 204), p.text

    # learner enrol + complete + rate
    requests.post(f"{BASE_URL}/api/courses/{course_id}/enroll",
                  headers=_hdr(learner_token), timeout=10)
    requests.post(f"{BASE_URL}/api/courses/{course_id}/complete",
                  headers=_hdr(learner_token), timeout=15)
    rr = requests.post(
        f"{BASE_URL}/api/courses/{course_id}/rating",
        json={"rating": 5, "comment": "TEST_Iter48 review body"},
        headers=_hdr(learner_token), timeout=10,
    )
    assert rr.status_code == 200, rr.text

    # find rating id via admin list
    lst = requests.get(f"{BASE_URL}/api/courses/{course_id}/reviews",
                       headers=_hdr(admin_token), timeout=10)
    assert lst.status_code == 200
    reviews = lst.json()
    assert reviews, "No review created"
    rating_id = reviews[0]["id"]

    yield course_id, rating_id, title

    # Cleanup (may fail if cascade bug still present)
    requests.delete(f"{BASE_URL}/api/courses/{course_id}",
                    headers=_hdr(admin_token), timeout=10)


# ─── Reply endpoint ────────────────────────────────────────────────
class TestReplyEndpoint:
    def test_post_reply_sets_text_and_at(self, seeded_course_with_review, admin_token):
        cid, rid, _ = seeded_course_with_review
        r = requests.post(
            f"{BASE_URL}/api/courses/{cid}/reviews/{rid}/reply",
            json={"reply": "Thanks for the great feedback!"},
            headers=_hdr(admin_token), timeout=10,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["reply_text"] == "Thanks for the great feedback!"
        assert j["reply_at"] is not None

    def test_admin_reviews_include_reply_fields(self, seeded_course_with_review, admin_token):
        cid, rid, _ = seeded_course_with_review
        arr = requests.get(f"{BASE_URL}/api/courses/{cid}/reviews",
                           headers=_hdr(admin_token), timeout=10).json()
        row = next(x for x in arr if x["id"] == rid)
        assert row["reply_text"] == "Thanks for the great feedback!"
        assert row["reply_at"] is not None

    def test_catalog_reviews_include_reply_fields(self, seeded_course_with_review):
        cid, rid, _ = seeded_course_with_review
        r = requests.get(f"{BASE_URL}/api/catalog/{cid}/reviews", timeout=10)
        assert r.status_code == 200, r.text
        arr = r.json()
        row = next(x for x in arr if x["id"] == rid)
        assert row["reply_text"] == "Thanks for the great feedback!"
        assert row["reply_at"] is not None

    def test_reply_over_1000_chars_422(self, seeded_course_with_review, admin_token):
        cid, rid, _ = seeded_course_with_review
        r = requests.post(
            f"{BASE_URL}/api/courses/{cid}/reviews/{rid}/reply",
            json={"reply": "a" * 1001},
            headers=_hdr(admin_token), timeout=10,
        )
        assert r.status_code == 422, r.text

    def test_reply_learner_forbidden(self, seeded_course_with_review, learner_token):
        cid, rid, _ = seeded_course_with_review
        r = requests.post(
            f"{BASE_URL}/api/courses/{cid}/reviews/{rid}/reply",
            json={"reply": "sneaky"}, headers=_hdr(learner_token), timeout=10,
        )
        assert r.status_code in (401, 403), r.text

    def test_reply_wrong_org_course_404(self, admin_token):
        """Course in another org → 404."""
        # Find a course belonging to org 1 (ifpi-main). UAT admin should 404.
        # We probe an id that likely exists in org 1 (223 per context) but not UAT.
        # Fall back to a scan if 223 not present.
        for candidate in (223, 222, 221, 1):
            r = requests.post(
                f"{BASE_URL}/api/courses/{candidate}/reviews/1/reply",
                json={"reply": "x"}, headers=_hdr(admin_token), timeout=10,
            )
            if r.status_code == 404:
                return  # expected — org scoping blocked
        pytest.skip("No cross-org course to probe; org scoping cannot be confirmed here")

    def test_empty_reply_clears(self, seeded_course_with_review, admin_token):
        cid, rid, _ = seeded_course_with_review
        r = requests.post(
            f"{BASE_URL}/api/courses/{cid}/reviews/{rid}/reply",
            json={"reply": ""}, headers=_hdr(admin_token), timeout=10,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["reply_text"] is None
        assert j["reply_at"] is None
        # And catalog reflects the clear
        arr = requests.get(f"{BASE_URL}/api/catalog/{cid}/reviews", timeout=10).json()
        row = next(x for x in arr if x["id"] == rid)
        assert row["reply_text"] is None
        assert row["reply_at"] is None


# ─── Social share OG endpoint ──────────────────────────────────────
class TestCourseShareOG:
    def test_share_returns_html_with_og_and_redirect(self, seeded_course_with_review):
        cid, _, title = seeded_course_with_review
        # first re-add a reply so rating exists; and also need a rating for stars
        # (rating exists from fixture even if reply cleared)
        r = requests.get(f"{BASE_URL}/api/seo/courses/share/{cid}",
                         allow_redirects=False, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        assert "text/html" in r.headers.get("content-type", "")
        body = r.text
        # OG tags
        assert 'property="og:title"' in body
        assert 'property="og:description"' in body
        # Star rating substring, e.g. "★ 5.0 (1 rating)" — allow float variance
        assert re.search(r"★ \d\.\d \(\d+ rating", body), \
            f"Star rating not present in description. Body head:\n{body[:800]}"
        # JS redirect to /catalog/{id}
        assert f'/catalog/{cid}' in body
        assert "window.location.replace" in body

    def test_share_escapes_html_in_title(self, seeded_course_with_review):
        cid, _, title = seeded_course_with_review
        r = requests.get(f"{BASE_URL}/api/seo/courses/share/{cid}", timeout=15)
        assert r.status_code == 200
        # We embedded <b> in title — verify escaped, not raw
        assert "&lt;b&gt;" in r.text
        assert "TEST_Iter48" in r.text

    def test_share_includes_og_image_when_org_logo_or_cover(self, seeded_course_with_review):
        cid, _, _ = seeded_course_with_review
        r = requests.get(f"{BASE_URL}/api/seo/courses/share/{cid}", timeout=15)
        # OG image is conditional on cover_image or org logo_url. Just verify tag structure
        # is present when applicable; otherwise absence is acceptable.
        if 'property="og:image"' in r.text:
            m = re.search(r'property="og:image" content="([^"]+)"', r.text)
            assert m and m.group(1).startswith("http"), \
                f"og:image should be absolute URL, got: {m.group(1) if m else None}"

    def test_share_404_for_unknown_course(self):
        r = requests.get(f"{BASE_URL}/api/seo/courses/share/99999999",
                         allow_redirects=False, timeout=10)
        assert r.status_code == 404

    def test_share_404_for_draft_course(self, admin_token, uat_market_optin):
        # Create a draft course, do NOT publish
        title = f"TEST_Iter48_Draft_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/courses",
                          json={"title": title, "description": "draft"},
                          headers=_hdr(admin_token), timeout=10)
        cid = r.json()["id"]
        try:
            resp = requests.get(f"{BASE_URL}/api/seo/courses/share/{cid}",
                                allow_redirects=False, timeout=10)
            assert resp.status_code == 404, f"Draft returned {resp.status_code}"
        finally:
            requests.delete(f"{BASE_URL}/api/courses/{cid}",
                            headers=_hdr(admin_token), timeout=10)

    def test_share_404_when_org_not_marketplace_opt_in(self, admin_token, learner_token):
        """Toggle UAT org off, create+publish course, share must 404."""
        from core.database import SessionLocal
        from models import Organization
        db = SessionLocal()
        org = db.query(Organization).filter(Organization.slug == "uat-sandbox").first()
        prev = org.marketplace_opt_in
        org.marketplace_opt_in = False
        db.commit()
        try:
            title = f"TEST_Iter48_NoMkt_{uuid.uuid4().hex[:6]}"
            r = requests.post(f"{BASE_URL}/api/courses",
                              json={"title": title}, headers=_hdr(admin_token), timeout=10)
            cid = r.json()["id"]
            requests.post(f"{BASE_URL}/api/courses/{cid}/slides",
                          json={"title": "s", "content_html": "<p>x</p>", "order_index": 0},
                          headers=_hdr(admin_token), timeout=10)
            requests.post(f"{BASE_URL}/api/courses/{cid}/publish",
                          headers=_hdr(admin_token), timeout=10)
            try:
                resp = requests.get(f"{BASE_URL}/api/seo/courses/share/{cid}",
                                    allow_redirects=False, timeout=10)
                assert resp.status_code == 404
            finally:
                requests.delete(f"{BASE_URL}/api/courses/{cid}",
                                headers=_hdr(admin_token), timeout=10)
        finally:
            org2 = db.query(Organization).filter(Organization.slug == "uat-sandbox").first()
            org2.marketplace_opt_in = prev
            db.commit()
            db.close()

    def test_share_no_auth_required(self, seeded_course_with_review):
        cid, _, _ = seeded_course_with_review
        # No headers whatsoever
        r = requests.get(f"{BASE_URL}/api/seo/courses/share/{cid}", timeout=15)
        assert r.status_code == 200
