"""Iteration 58 — Slide image_position + bulk photo upload backend tests."""


import os
import io
import pytest

# Skip integration tests that hit a live external API when running in CI.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip external integration tests in CI",
)

import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "uat-admin@ifpi.org"
ADMIN_PASSWORD = "UatAdmin!2026"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token")
    assert tok, f"no access_token in response body: {data}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def draft_course(admin_headers):
    """Create a test draft course; delete at teardown."""
    import time
    title = f"TEST_ImgPos_{int(time.time())}"
    r = requests.post(f"{BASE_URL}/api/courses", headers=admin_headers,
                      json={"title": title, "description": "iter58 test",
                            "category": "Test", "status": "DRAFT"})
    assert r.status_code == 200, r.text
    course = r.json()
    yield course
    # cleanup
    try:
        cid = course["id"]
        # ensure not published
        requests.post(f"{BASE_URL}/api/courses/{cid}/unpublish", headers=admin_headers)
        d = requests.delete(f"{BASE_URL}/api/courses/{cid}", headers=admin_headers)
        print(f"Cleanup DELETE course {cid} -> {d.status_code}")
    except Exception as e:
        print(f"cleanup err: {e}")


class TestSlideImagePosition:

    def test_create_slide_with_beside(self, admin_headers, draft_course):
        cid = draft_course["id"]
        r = requests.post(f"{BASE_URL}/api/courses/{cid}/slides", headers=admin_headers,
                          json={"title": "S1", "content": "c", "slide_type": "IMAGE",
                                "media_url": "/uploads/dummy.png",
                                "image_position": "beside"})
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["image_position"] == "beside"
        # verify via GET
        g = requests.get(f"{BASE_URL}/api/courses/{cid}", headers=admin_headers)
        assert g.status_code == 200
        slide = next(x for x in g.json()["slides"] if x["id"] == s["id"])
        assert slide["image_position"] == "beside"

    def test_patch_slide_to_behind(self, admin_headers, draft_course):
        cid = draft_course["id"]
        r = requests.post(f"{BASE_URL}/api/courses/{cid}/slides", headers=admin_headers,
                          json={"title": "S2", "slide_type": "IMAGE",
                                "media_url": "/uploads/dummy2.png",
                                "image_position": "above"})
        assert r.status_code == 200
        sid = r.json()["id"]
        u = requests.patch(f"{BASE_URL}/api/courses/{cid}/slides/{sid}",
                          headers=admin_headers,
                          json={"title": "S2", "slide_type": "IMAGE",
                                "media_url": "/uploads/dummy2.png",
                                "image_position": "behind"})
        assert u.status_code == 200, u.text
        assert u.json()["image_position"] == "behind"
        # persistence check
        g = requests.get(f"{BASE_URL}/api/courses/{cid}", headers=admin_headers)
        slide = next(x for x in g.json()["slides"] if x["id"] == sid)
        assert slide["image_position"] == "behind"

    def test_invalid_position_falls_back_to_above(self, admin_headers, draft_course):
        cid = draft_course["id"]
        r = requests.post(f"{BASE_URL}/api/courses/{cid}/slides", headers=admin_headers,
                          json={"title": "S3", "slide_type": "IMAGE",
                                "media_url": "/uploads/dummy3.png",
                                "image_position": "diagonal"})
        assert r.status_code == 200
        assert r.json()["image_position"] == "above"

    def test_get_course_includes_image_position(self, admin_headers, draft_course):
        cid = draft_course["id"]
        g = requests.get(f"{BASE_URL}/api/courses/{cid}", headers=admin_headers)
        assert g.status_code == 200
        for s in g.json()["slides"]:
            assert "image_position" in s
            assert s["image_position"] in ("above", "beside", "behind")


class TestImageUpload:
    """Bulk photo upload underlying endpoint."""

    def test_image_upload_returns_url(self, admin_token):
        # 1x1 PNG
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
            "0000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
        )
        headers = {"Authorization": f"Bearer {admin_token}"}
        files = {"file": ("test.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{BASE_URL}/api/uploads/image", headers=headers, files=files)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        data = r.json()
        assert "url" in data, data
