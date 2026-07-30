"""Iter 43 — Landing page polish, cover gallery library, weekly enrolment analytics."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

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
        pytest.skip("2FA is enabled")
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


# ─────────────── Cover library ───────────────

def test_cover_library_returns_15_items(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/uploads/cover-library", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert len(items) == 15, f"expected 15 items, got {len(items)}"
    for it in items:
        assert "url" in it and "label" in it
        assert it["url"].startswith("/api/uploads/files/covers/library/")
        assert it["url"].endswith(".jpg")
        assert it["label"]


def test_cover_library_urls_fetchable(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/uploads/cover-library", timeout=15)
    items = r.json()
    items = items if isinstance(items, list) else items.get("items", [])
    for it in items[:5]:
        rr = requests.get(f"{BASE_URL}{it['url']}", timeout=15)
        assert rr.status_code == 200, f"{it['url']} -> {rr.status_code}"
        assert "image/jpeg" in rr.headers.get("Content-Type", "").lower()


def test_cover_library_learner_forbidden(uat_learner):
    r = uat_learner.get(f"{BASE_URL}/api/uploads/cover-library", timeout=15)
    assert r.status_code == 403, r.text


# ─────────────── Weekly enrolments ───────────────

def _iso_monday(dt: datetime) -> str:
    return (dt - timedelta(days=dt.weekday())).date().isoformat()


def test_weekly_enrollments_default_12(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "weeks" in data
    weeks = data["weeks"]
    assert len(weeks) == 12
    # Check consecutive Mondays
    prev = None
    for w in weeks:
        assert "week_start" in w and "count" in w
        assert isinstance(w["count"], int)
        d = datetime.fromisoformat(w["week_start"]).date()
        assert d.weekday() == 0, f"{w['week_start']} not Monday"
        if prev:
            assert (d - prev).days == 7
        prev = d
    # Last week is current week
    now = datetime.now(timezone.utc)
    assert weeks[-1]["week_start"] == _iso_monday(now)


def test_weekly_enrollments_weeks_8(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly?weeks=8", timeout=15)
    assert r.status_code == 200
    assert len(r.json()["weeks"]) == 8


def test_weekly_enrollments_invalid_below(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly?weeks=3", timeout=15)
    assert r.status_code == 422


def test_weekly_enrollments_invalid_above(uat_admin):
    r = uat_admin.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly?weeks=30", timeout=15)
    assert r.status_code == 422


def test_weekly_enrollments_learner_forbidden(uat_learner):
    r = uat_learner.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly", timeout=15)
    assert r.status_code == 403


# ─────────── Data correctness / org-scoping ───────────

def test_weekly_enrollments_org_scoping(uat_admin, uat_learner, main_admin):
    # Before counts
    def curr_count(sess):
        r = sess.get(f"{BASE_URL}/api/admin/analytics/enrollments-weekly", timeout=15)
        assert r.status_code == 200
        return r.json()["weeks"][-1]["count"]

    uat_before = curr_count(uat_admin)
    main_before = curr_count(main_admin)

    # Create TEST_ course in UAT org
    r = uat_admin.post(f"{BASE_URL}/api/courses",
                       json={"title": f"TEST_iter43 {uuid.uuid4().hex[:6]}",
                             "description": "weekly-enrollment scoping"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    enrollment_id = None
    try:
        # Insert TEST_ enrollment directly via DB (course cannot be published without slides)
        import sys
        sys.path.insert(0, "/app/backend")
        from core.database import SessionLocal  # type: ignore
        from models import Enrollment, User  # type: ignore
        db = SessionLocal()
        try:
            learner_row = db.query(User).filter_by(email="uat-learner@ifpi.org").first()
            e = Enrollment(user_id=learner_row.id, course_id=cid)
            db.add(e)
            db.commit()
            db.refresh(e)
            enrollment_id = e.id
        finally:
            db.close()

        uat_after = curr_count(uat_admin)
        main_after = curr_count(main_admin)

        assert uat_after == uat_before + 1, f"UAT current-week count did not increment: {uat_before}->{uat_after}"
        assert main_after == main_before, f"Main org count changed unexpectedly: {main_before}->{main_after}"
    finally:
        # Cleanup enrollment then course
        if enrollment_id:
            from core.database import SessionLocal  # type: ignore
            from models import Enrollment  # type: ignore
            db = SessionLocal()
            try:
                db.query(Enrollment).filter_by(id=enrollment_id).delete()
                db.commit()
            finally:
                db.close()
        uat_admin.delete(f"{BASE_URL}/api/courses/{cid}", timeout=15)


# ─────────────── Landing regression (public) ───────────────

def test_public_catalog_featured_still_works():
    r = requests.get(f"{BASE_URL}/api/catalog?featured=true", timeout=15,
                     headers={"X-Test-Client-Ip": f"testip-{uuid.uuid4()}"})
    assert r.status_code == 200
    data = r.json()
    courses = data if isinstance(data, list) else (
        data.get("featured") or data.get("courses") or data.get("items") or [])
    assert len(courses) >= 1
    for c in courses:
        assert c.get("cover_image")
