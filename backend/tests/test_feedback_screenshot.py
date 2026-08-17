"""Tests for feedback screenshot upload + tour-related backend paths (iter 57)."""


import io
import os
import struct
import zlib

import pytest

# Skip integration tests that hit a live external API when running in CI.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip external integration tests in CI",
)

import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://learning-hub-968.preview.emergentagent.com").rstrip("/")

LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}
ADMIN = {"email": "uat-admin@ifpi.org", "password": "UatAdmin!2026"}


def _tiny_png() -> bytes:
    # Minimal 1x1 PNG built manually
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\xff\xff"
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _login(payload):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def learner_token():
    return _login(LEARNER)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


def test_screenshot_upload_requires_auth():
    r = requests.post(f"{BASE_URL}/api/feedback/screenshot",
                      files={"file": ("a.png", _tiny_png(), "image/png")}, timeout=15)
    assert r.status_code == 401, f"expected 401, got {r.status_code}"


def test_screenshot_upload_rejects_non_image(learner_token):
    r = requests.post(
        f"{BASE_URL}/api/feedback/screenshot",
        headers={"Authorization": f"Bearer {learner_token}"},
        files={"file": ("a.txt", b"hello world", "text/plain")}, timeout=15,
    )
    assert r.status_code == 400, f"expected 400 got {r.status_code} body={r.text}"


def test_screenshot_upload_success_and_serves(learner_token):
    png = _tiny_png()
    r = requests.post(
        f"{BASE_URL}/api/feedback/screenshot",
        headers={"Authorization": f"Bearer {learner_token}"},
        files={"file": ("test.png", png, "image/png")}, timeout=20,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "url" in body and "/feedback/" in body["url"]
    # Fetch the image
    url = body["url"] if body["url"].startswith("http") else f"{BASE_URL}{body['url']}"
    img = requests.get(url, timeout=15)
    assert img.status_code == 200, f"image fetch got {img.status_code}"
    assert img.headers.get("content-type", "").startswith("image/")


def test_submit_feedback_with_screenshot(learner_token):
    # upload first
    up = requests.post(
        f"{BASE_URL}/api/feedback/screenshot",
        headers={"Authorization": f"Bearer {learner_token}"},
        files={"file": ("s.png", _tiny_png(), "image/png")}, timeout=15,
    )
    assert up.status_code == 201
    url = up.json()["url"]
    r = requests.post(
        f"{BASE_URL}/api/feedback",
        headers={"Authorization": f"Bearer {learner_token}"},
        json={"message": "TEST_ Automated feedback with shot", "category": "BUG",
              "page": "/courses", "screenshot_url": url}, timeout=15,
    )
    assert r.status_code == 201, r.text
    assert r.json().get("ok") is True


def test_submit_feedback_no_screenshot(learner_token):
    r = requests.post(
        f"{BASE_URL}/api/feedback",
        headers={"Authorization": f"Bearer {learner_token}"},
        json={"message": "TEST_ Automated msg only", "category": "IDEA", "page": "/courses"}, timeout=15,
    )
    assert r.status_code == 201, r.text


def test_submit_feedback_invalid_screenshot_url_rejected(learner_token):
    r = requests.post(
        f"{BASE_URL}/api/feedback",
        headers={"Authorization": f"Bearer {learner_token}"},
        json={"message": "TEST_ bad shot", "category": "BUG",
              "screenshot_url": "https://evil.example.com/img.png"}, timeout=15,
    )
    assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"


def test_admin_list_returns_screenshot_url(admin_token, learner_token):
    # Ensure at least one feedback with screenshot exists
    up = requests.post(
        f"{BASE_URL}/api/feedback/screenshot",
        headers={"Authorization": f"Bearer {learner_token}"},
        files={"file": ("s.png", _tiny_png(), "image/png")}, timeout=15,
    )
    url = up.json()["url"]
    requests.post(
        f"{BASE_URL}/api/feedback",
        headers={"Authorization": f"Bearer {learner_token}"},
        json={"message": "TEST_ admin list check", "category": "BUG", "screenshot_url": url}, timeout=15,
    )
    r = requests.get(f"{BASE_URL}/api/admin/feedback",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    assert any(row.get("screenshot_url") for row in rows), "no rows with screenshot_url"
    # keys sanity
    r0 = rows[0]
    for k in ("id", "message", "category", "status", "screenshot_url"):
        assert k in r0


def test_admin_toggle_status(admin_token, learner_token):
    # create a fresh row
    r = requests.post(f"{BASE_URL}/api/feedback",
                      headers={"Authorization": f"Bearer {learner_token}"},
                      json={"message": "TEST_ toggle status", "category": "OTHER"}, timeout=15)
    fid = r.json()["id"]
    r2 = requests.post(f"{BASE_URL}/api/admin/feedback/{fid}/status",
                       headers={"Authorization": f"Bearer {admin_token}"},
                       json={"status": "REVIEWED"}, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "REVIEWED"
