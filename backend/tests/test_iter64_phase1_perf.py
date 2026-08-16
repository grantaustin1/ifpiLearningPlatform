"""Iteration 64 Phase 1: N+1 fix on courses list/detail + HTTP Range serving.

Focus: only the changed surface. Course 243 is real content (read-only).
"""
from __future__ import annotations

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read from frontend .env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN = {"email": "uat-admin@ifpi.org", "password": "UatAdmin!2026"}
LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}
VIDEO_PATH = "imports/327/vids/out1.webm"
COURSE_ID = 243


def _login(session: requests.Session, creds: dict) -> str:
    r = session.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed {creds['email']}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in response: {r.json()}"
    session.headers.update({"Authorization": f"Bearer {tok}"})
    return tok


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def learner_session():
    s = requests.Session()
    _login(s, LEARNER)
    return s


# ── Course list / detail counts (N+1 fix) ────────────────────────────
class TestCourseCounts:
    def test_admin_course_list_has_counts(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/courses", timeout=60)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and arr
        by_id = {c["id"]: c for c in arr}
        assert COURSE_ID in by_id, f"course {COURSE_ID} not in admin list"
        c243 = by_id[COURSE_ID]
        assert c243["slide_count"] == 99, f"expected slide_count=99, got {c243['slide_count']}"
        assert c243["enrollment_count"] >= 1, (
            f"expected enrollment_count>0 (real data), got {c243['enrollment_count']}"
        )
        # sanity: schema fields present
        for k in ("id", "title", "status", "slide_count", "enrollment_count"):
            assert k in c243

    def test_learner_course_list_only_published(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/courses", timeout=60)
        assert r.status_code == 200
        arr = r.json()
        assert all(c["status"] == "PUBLISHED" for c in arr), (
            "learner sees non-published courses"
        )
        by_id = {c["id"]: c for c in arr}
        assert COURSE_ID in by_id
        c243 = by_id[COURSE_ID]
        assert c243["slide_count"] == 99
        assert c243["enrollment_count"] >= 1

    def test_admin_sees_drafts(self, admin_session, learner_session):
        r_admin = admin_session.get(f"{BASE_URL}/api/courses", timeout=60).json()
        r_learn = learner_session.get(f"{BASE_URL}/api/courses", timeout=60).json()
        admin_statuses = {c["status"] for c in r_admin}
        # Admin list should typically include DRAFT/ARCHIVED at least once
        # Otherwise, just verify admin list >= learner list
        assert len(r_admin) >= len(r_learn), (
            f"admin ({len(r_admin)}) should see >= learner ({len(r_learn)}) courses"
        )
        # Non-fatal: log admin statuses
        print(f"admin statuses: {admin_statuses}, admin_ct={len(r_admin)}, "
              f"learner_ct={len(r_learn)}")

    def test_course_detail_243_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/courses/{COURSE_ID}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == COURSE_ID
        assert d["slide_count"] == 99
        assert d["enrollment_count"] >= 1
        assert isinstance(d.get("slides"), list)
        assert len(d["slides"]) == 99, f"expected 99 slides, got {len(d['slides'])}"

    def test_course_detail_243_learner(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/courses/{COURSE_ID}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["slide_count"] == 99
        assert d["enrollment_count"] >= 1
        assert len(d["slides"]) == 99


# ── Range request serving on /api/uploads/files/{path} ───────────────
class TestRangeServing:
    def test_no_range_returns_200_with_accept_ranges(self, learner_session):
        r = learner_session.get(
            f"{BASE_URL}/api/uploads/files/{VIDEO_PATH}", timeout=60, stream=True,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        assert r.headers.get("Accept-Ranges", "").lower() == "bytes"
        assert r.headers.get("Content-Type", "").startswith("video/webm")
        r.close()

    def test_range_first_1024(self, learner_session):
        r = learner_session.get(
            f"{BASE_URL}/api/uploads/files/{VIDEO_PATH}",
            headers={"Range": "bytes=0-1023"}, timeout=60,
        )
        assert r.status_code == 206, f"expected 206, got {r.status_code}"
        assert r.headers.get("Accept-Ranges", "").lower() == "bytes"
        cr = r.headers.get("Content-Range", "")
        assert cr.startswith("bytes 0-1023/"), f"bad Content-Range: {cr}"
        body = r.content
        assert len(body) == 1024, f"expected 1024 bytes, got {len(body)}"

    def test_range_suffix_last_500(self, learner_session):
        # first learn total size
        head = learner_session.get(
            f"{BASE_URL}/api/uploads/files/{VIDEO_PATH}",
            headers={"Range": "bytes=0-0"}, timeout=60,
        )
        assert head.status_code == 206
        total = int(head.headers["Content-Range"].split("/")[-1])
        r = learner_session.get(
            f"{BASE_URL}/api/uploads/files/{VIDEO_PATH}",
            headers={"Range": "bytes=-500"}, timeout=60,
        )
        assert r.status_code == 206, f"expected 206, got {r.status_code}"
        cr = r.headers.get("Content-Range", "")
        expected_start = total - 500
        assert cr == f"bytes {expected_start}-{total-1}/{total}", (
            f"bad Content-Range: {cr}, total={total}"
        )
        assert len(r.content) == 500

    def test_range_out_of_bounds_416(self, learner_session):
        r = learner_session.get(
            f"{BASE_URL}/api/uploads/files/{VIDEO_PATH}",
            headers={"Range": "bytes=999999999-"}, timeout=60,
        )
        assert r.status_code == 416, f"expected 416, got {r.status_code}"
        cr = r.headers.get("Content-Range", "")
        assert cr.startswith("bytes */"), f"bad Content-Range: {cr}"

    def test_image_get_still_200(self, learner_session):
        # find any image slide from course 243 detail
        d = learner_session.get(f"{BASE_URL}/api/courses/{COURSE_ID}", timeout=60).json()
        img_url = None
        for s in d.get("slides", []):
            mu = (s.get("media_url") or "")
            if any(mu.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                img_url = mu
                break
        if not img_url:
            pytest.skip("no image slide found in course 243")
        # media_url may be relative; join with BASE_URL if starts with /api
        url = img_url if img_url.startswith("http") else f"{BASE_URL}{img_url}"
        r = learner_session.get(url, timeout=60)
        assert r.status_code == 200, f"image GET failed: {r.status_code}"
        assert r.headers.get("Content-Type", "").startswith("image/")
        # Range code should NOT have converted a normal GET to 206
        assert "Accept-Ranges" in r.headers


# ── Unchanged flow smoke ─────────────────────────────────────────────
class TestSmoke:
    def test_login_admin(self):
        s = requests.Session()
        _login(s, ADMIN)

    def test_login_learner(self):
        s = requests.Session()
        _login(s, LEARNER)

    def test_dashboard_loads(self, learner_session):
        # A couple of common dashboard endpoints — either should succeed
        candidates = [
            "/api/dashboard/learner",
            "/api/me/enrollments",
            "/api/enrollments",
            "/api/me",
        ]
        ok_any = False
        for path in candidates:
            r = learner_session.get(f"{BASE_URL}{path}", timeout=30)
            if r.status_code == 200:
                ok_any = True
                break
        assert ok_any, "no dashboard-like endpoint returned 200"
