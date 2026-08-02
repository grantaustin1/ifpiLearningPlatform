"""Iter 44 — In-app feedback widget, course ratings, dashboard chart toggle."""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password},
               headers={"X-Return-Token": "true"}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("2FA enabled")
    token = body.get("access_token")
    if not token:
        pytest.skip(f"no access_token: {body}")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def uat_admin():
    return _login("uat-admin@ifpi.org", "UatAdmin!2026")


@pytest.fixture(scope="module")
def uat_learner():
    return _login("uat-learner@ifpi.org", "UatLearner!2026")


@pytest.fixture(scope="module")
def main_admin():
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture(scope="module")
def main_learner():
    return _login("learner@ifpi.org", "learner123")


# ─────────────── Feedback API ───────────────

def test_feedback_submit_success(uat_learner):
    r = uat_learner.post(f"{BASE_URL}/api/feedback",
                         json={"message": f"TEST_iter44 feedback {uuid.uuid4().hex[:6]}",
                               "category": "IDEA", "page": "/dashboard"}, timeout=15)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("id"), int)


def test_feedback_bad_category(uat_learner):
    r = uat_learner.post(f"{BASE_URL}/api/feedback",
                         json={"message": "TEST_ bad cat here", "category": "NOPE"}, timeout=15)
    assert r.status_code == 422, r.text


def test_feedback_short_message(uat_learner):
    r = uat_learner.post(f"{BASE_URL}/api/feedback",
                         json={"message": "hi", "category": "BUG"}, timeout=15)
    assert r.status_code == 422, r.text


def test_feedback_unauthenticated():
    r = requests.post(f"{BASE_URL}/api/feedback",
                      json={"message": "TEST_ anonymous try", "category": "BUG"}, timeout=15)
    assert r.status_code in (401, 403), r.text


# ─────────────── Feedback admin ───────────────

def test_feedback_admin_list(uat_admin, uat_learner):
    # Ensure at least one item
    msg = f"TEST_iter44 admin-list {uuid.uuid4().hex[:6]}"
    r = uat_learner.post(f"{BASE_URL}/api/feedback",
                         json={"message": msg, "category": "BUG"}, timeout=15)
    assert r.status_code == 201

    r = uat_admin.get(f"{BASE_URL}/api/admin/feedback", timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) >= 1
    # Newest first: first row is the one we just created
    assert rows[0]["message"] == msg
    assert rows[0]["user_email"] == "uat-learner@ifpi.org"
    assert "user_name" in rows[0]
    assert rows[0]["status"] == "NEW"
    # descending created_at (dates monotonically non-increasing)
    dates = [r_["created_at"] for r_ in rows]
    assert dates == sorted(dates, reverse=True)


def test_feedback_admin_status_toggle(uat_admin, uat_learner):
    r = uat_learner.post(f"{BASE_URL}/api/feedback",
                         json={"message": f"TEST_iter44 toggle {uuid.uuid4().hex[:6]}",
                               "category": "OTHER"}, timeout=15)
    fid = r.json()["id"]

    r = uat_admin.post(f"{BASE_URL}/api/admin/feedback/{fid}/status",
                       json={"status": "REVIEWED"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REVIEWED"

    # Verify persistence
    rows = uat_admin.get(f"{BASE_URL}/api/admin/feedback", timeout=15).json()
    match = next((x for x in rows if x["id"] == fid), None)
    assert match and match["status"] == "REVIEWED"

    # Flip back
    r = uat_admin.post(f"{BASE_URL}/api/admin/feedback/{fid}/status",
                       json={"status": "NEW"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "NEW"


def test_feedback_admin_learner_forbidden(uat_learner):
    r = uat_learner.get(f"{BASE_URL}/api/admin/feedback", timeout=15)
    assert r.status_code == 403


def test_feedback_org_isolation(main_admin, uat_learner):
    """MAIN admin must NOT see UAT feedback items."""
    # Create a UAT-scoped feedback with a unique marker
    marker = f"TEST_iter44 UAT-only-{uuid.uuid4().hex[:8]}"
    uat_learner.post(f"{BASE_URL}/api/feedback",
                     json={"message": marker, "category": "BUG"}, timeout=15)

    r = main_admin.get(f"{BASE_URL}/api/admin/feedback", timeout=15)
    assert r.status_code == 200
    rows = r.json()
    messages = [x["message"] for x in rows]
    assert marker not in messages, "MAIN admin should not see UAT feedback"
    # Should not contain any UAT users either
    emails = {x["user_email"] for x in rows}
    assert "uat-learner@ifpi.org" not in emails
    assert "uat-admin@ifpi.org" not in emails


# ─────────────── Ratings API ───────────────

def _make_course_with_slide(admin_sess):
    """Create a small TEST_ course with one slide and PUBLISH it."""
    r = admin_sess.post(f"{BASE_URL}/api/courses",
                        json={"title": f"TEST_iter44 rating {uuid.uuid4().hex[:6]}",
                              "description": "rating tests"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]

    # Add a slide
    r = admin_sess.post(f"{BASE_URL}/api/courses/{cid}/slides",
                        json={"title": "TEST slide", "content": "hello",
                              "slide_type": "TEXT", "order_index": 1}, timeout=15)
    assert r.status_code in (200, 201), r.text

    # Publish
    r = admin_sess.patch(f"{BASE_URL}/api/courses/{cid}",
                         json={"status": "PUBLISHED"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    return cid


@pytest.fixture(scope="module")
def uat_course(uat_admin):
    cid = _make_course_with_slide(uat_admin)
    yield cid
    try:
        uat_admin.delete(f"{BASE_URL}/api/courses/{cid}", timeout=15)
    except Exception:
        pass


def test_rating_before_completion_forbidden(uat_learner, uat_course):
    # Ensure the learner has NOT completed. Best-effort clean any enrollment.
    r = uat_learner.post(f"{BASE_URL}/api/courses/{uat_course}/rating",
                         json={"rating": 5}, timeout=15)
    assert r.status_code == 403, r.text


def test_rating_invalid_values(uat_learner, uat_course):
    for bad in [0, 6, "5", 3.5, None]:
        r = uat_learner.post(f"{BASE_URL}/api/courses/{uat_course}/rating",
                             json={"rating": bad}, timeout=15)
        assert r.status_code == 422, f"rating={bad!r} -> {r.status_code} {r.text}"


def test_rating_after_completion_and_upsert(uat_learner, uat_course):
    # Enrol + complete via the API
    r = uat_learner.post(f"{BASE_URL}/api/courses/{uat_course}/enroll", timeout=15)
    assert r.status_code in (200, 201), r.text
    r = uat_learner.post(f"{BASE_URL}/api/courses/{uat_course}/complete", timeout=15)
    assert r.status_code in (200, 201), r.text

    # Rate 4
    r = uat_learner.post(f"{BASE_URL}/api/courses/{uat_course}/rating",
                         json={"rating": 4}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("my_rating") == 4
    assert data.get("rating_count") == 1
    assert data.get("avg_rating") == 4.0

    # Re-rate 5 (upsert; count stays 1)
    r = uat_learner.post(f"{BASE_URL}/api/courses/{uat_course}/rating",
                         json={"rating": 5}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["my_rating"] == 5
    assert data["rating_count"] == 1
    assert data["avg_rating"] == 5.0

    # GET rating
    r = uat_learner.get(f"{BASE_URL}/api/courses/{uat_course}/rating", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["my_rating"] == 5
    assert data["rating_count"] == 1
    assert data["avg_rating"] == 5.0


# ─────────────── Catalog stars ───────────────

def test_catalog_includes_rating_fields():
    r = requests.get(f"{BASE_URL}/api/catalog", timeout=15,
                     headers={"X-Test-Client-Ip": f"testip-{uuid.uuid4()}"})
    assert r.status_code == 200, r.text
    data = r.json()
    courses = data.get("courses") if isinstance(data, dict) else data
    assert isinstance(courses, list) and len(courses) >= 1
    for c in courses:
        assert "avg_rating" in c
        assert "rating_count" in c
        assert isinstance(c["rating_count"], int)


# ─────────────── Weekly chart toggle ───────────────

def test_weekly_completions_metric(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly?metric=completions",
                      timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "weeks" in data and len(data["weeks"]) == 12
    for w in data["weeks"]:
        assert "week_start" in w and isinstance(w["count"], int)


def test_weekly_enrollments_metric_default(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly?metric=enrollments",
                      timeout=15)
    assert r.status_code == 200
    assert len(r.json()["weeks"]) == 12


def test_weekly_bogus_metric_422(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly?metric=bogus",
                      timeout=15)
    assert r.status_code == 422
