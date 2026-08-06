"""Iter 42 — Course cover images + Featured Course Pick."""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module", autouse=True)
def _purge_debris_first():
    """Earlier suite files (Stripe/entitlement harnesses) leave debris
    courses behind — purge them so catalog assertions see a clean state."""
    from core.database import SessionLocal
    from services.test_debris_cleanup import tick
    with SessionLocal() as db:
        tick(db)
        db.commit()
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
        pytest.skip("2FA is enabled — clear first")
    token = body.get("access_token")
    if not token:
        pytest.skip(f"no access_token in login response: {body}")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture
def admin():
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner():
    return _login("learner@ifpi.org", "learner123")


@pytest.fixture
def uat_admin():
    return _login("uat-admin@ifpi.org", "UatAdmin!2026")


# ---------------- Public catalog ----------------

def test_catalog_returns_courses_with_cover_and_featured():
    r = requests.get(f"{BASE_URL}/api/catalog", timeout=15,
                     headers={"X-Test-Client-Ip": f"testip-{uuid.uuid4()}"})
    assert r.status_code == 200, r.text
    data = r.json()
    # catalog may return dict with sections or list — handle both
    courses = data if isinstance(data, list) else (
        data.get("courses") or data.get("all") or data.get("items") or [])
    assert len(courses) >= 4, f"expected >=4 courses, got {len(courses)}: {data}"
    for c in courses:
        assert "cover_image" in c, f"missing cover_image in {c}"
        assert "is_featured" in c, f"missing is_featured in {c}"
        assert c["cover_image"], f"cover_image blank for {c.get('title')}"
        assert "/api/uploads/files/covers/" in c["cover_image"]


def test_catalog_cover_image_is_public_jpeg():
    r = requests.get(f"{BASE_URL}/api/catalog", timeout=15,
                     headers={"X-Test-Client-Ip": f"testip-{uuid.uuid4()}"})
    data = r.json()
    courses = data if isinstance(data, list) else (
        data.get("courses") or data.get("all") or data.get("items") or [])
    tested = 0
    for c in courses[:4]:
        img = c["cover_image"]
        url = img if img.startswith("http") else f"{BASE_URL}{img}"
        rr = requests.get(url, timeout=15)
        assert rr.status_code == 200, f"{url} -> {rr.status_code}"
        assert "image" in rr.headers.get("Content-Type", "").lower()
        tested += 1
    assert tested >= 1


def test_catalog_featured_flag_first():
    r = requests.get(f"{BASE_URL}/api/catalog?featured=true", timeout=15,
                     headers={"X-Test-Client-Ip": f"testip-{uuid.uuid4()}"})
    assert r.status_code == 200, r.text
    data = r.json()
    courses = data if isinstance(data, list) else (
        data.get("featured") or data.get("courses") or data.get("items") or [])
    assert len(courses) >= 1
    # course 222 must appear first (flagged)
    first = courses[0]
    assert first.get("id") == 222, f"expected course 222 first, got {first}"
    assert first.get("is_featured") is True


# ---------------- Toggle endpoint / RBAC ----------------

def test_toggle_featured_admin_flips_twice(admin):
    # get current
    r = admin.get(f"{BASE_URL}/api/courses/222", timeout=15)
    assert r.status_code == 200
    original = r.json().get("is_featured")

    r1 = admin.post(f"{BASE_URL}/api/courses/222/toggle-featured", timeout=15)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["id"] == 222
    assert b1["is_featured"] == (not original)

    r2 = admin.post(f"{BASE_URL}/api/courses/222/toggle-featured", timeout=15)
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["is_featured"] == original

    # verify persistence via GET
    r = admin.get(f"{BASE_URL}/api/courses/222", timeout=15)
    assert r.json().get("is_featured") == original
    # Ensure 222 ends flagged true (per instructions)
    if not original:
        admin.post(f"{BASE_URL}/api/courses/222/toggle-featured", timeout=15)


def test_toggle_featured_learner_forbidden(learner):
    r = learner.post(f"{BASE_URL}/api/courses/222/toggle-featured", timeout=15)
    assert r.status_code == 403, r.text


def test_toggle_featured_other_org_admin_404(uat_admin):
    r = uat_admin.post(f"{BASE_URL}/api/courses/222/toggle-featured", timeout=15)
    assert r.status_code == 404, r.text


# ---------------- Course update: cover_image ----------------

def test_admin_can_patch_cover_image(admin):
    # create TEST_ course
    payload = {
        "title": f"TEST_iter42 cover {uuid.uuid4().hex[:6]}",
        "description": "cover-image patch test",
    }
    r = admin.post(f"{BASE_URL}/api/courses", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    try:
        new_cover = "/api/uploads/files/covers/exercise_science.jpg"
        r = admin.patch(f"{BASE_URL}/api/courses/{cid}",
                        json={"cover_image": new_cover}, timeout=15)
        assert r.status_code in (200, 204), r.text
        r = admin.get(f"{BASE_URL}/api/courses/{cid}", timeout=15)
        assert r.status_code == 200
        assert r.json().get("cover_image") == new_cover
    finally:
        admin.delete(f"{BASE_URL}/api/courses/{cid}", timeout=15)


def test_course_222_ends_featured(admin):
    """Ensure course 222 remains featured=true at end (safety net)."""
    r = admin.get(f"{BASE_URL}/api/courses/222", timeout=15)
    if r.status_code == 200 and not r.json().get("is_featured"):
        admin.post(f"{BASE_URL}/api/courses/222/toggle-featured", timeout=15)
    r = admin.get(f"{BASE_URL}/api/courses/222", timeout=15)
    assert r.json().get("is_featured") is True
