"""Iter 30b — Redis rate limiter + PDF verify link + mind-map thumbnails."""
from __future__ import annotations

import base64
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _login("learner@ifpi.org", "learner123")


# ── Mind-map thumbnail persistence + surfacing on course list ───────
def _tiny_svg_b64() -> str:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120">'
           '<circle cx="100" cy="60" r="40" fill="#6366f1"/></svg>')
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def test_mindmap_thumbnail_persists_and_shows_on_summary(admin):
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    layout = {
        "graph": {"root": {"id": "root", "label": "Course"},
                  "topics": [{"id": "t1", "label": "Intro"}]},
        "positions": {"root": {"x": 500, "y": 300}, "t1": {"x": 700, "y": 300}},
        "thumbnail_svg": _tiny_svg_b64(),
    }
    r = admin.put(f"{BASE_URL}/api/authoring/mindmap/{course['id']}/layout",
                  json=layout, timeout=10)
    assert r.status_code == 200

    # Course summary now carries the thumbnail
    listing = admin.get(f"{BASE_URL}/api/courses", timeout=10).json()
    hit = next((c for c in listing if c["id"] == course["id"]), None)
    assert hit is not None
    assert hit.get("mindmap_thumbnail_svg") == _tiny_svg_b64()

    # Course detail also carries it
    detail = admin.get(f"{BASE_URL}/api/courses/{course['id']}", timeout=10).json()
    assert detail.get("mindmap_thumbnail_svg") == _tiny_svg_b64()

    # Clear layout also removes the thumbnail
    admin.delete(f"{BASE_URL}/api/authoring/mindmap/{course['id']}/layout", timeout=10)
    listing2 = admin.get(f"{BASE_URL}/api/courses", timeout=10).json()
    hit2 = next((c for c in listing2 if c["id"] == course["id"]), None)
    assert hit2.get("mindmap_thumbnail_svg") in (None, "")


def test_mindmap_thumbnail_rejects_oversized_payload(admin):
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    huge = "A" * 200_001  # > 200 KB pydantic max
    r = admin.put(f"{BASE_URL}/api/authoring/mindmap/{course['id']}/layout",
                  json={
                      "graph": {"root": {"id": "root", "label": "X"}, "topics": []},
                      "positions": {"root": {"x": 0, "y": 0}},
                      "thumbnail_svg": huge,
                  }, timeout=10)
    assert r.status_code == 422


# ── PDF verify link (Iter 30b) ──────────────────────────────────────
def test_cert_pdf_contains_verify_link_text(learner):
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    if not certs:
        pytest.skip("No certificates for learner")
    r = learner.get(f"{BASE_URL}/api/certificates/{certs[0]['id']}/pdf", timeout=30)
    assert r.status_code == 200
    body = r.content
    assert body[:4] == b"%PDF"
    # ReportLab embeds link annotations as `/URI (...)`. Absent the annotation
    # the substring won't appear.
    assert b"/URI" in body, "Expected clickable /URI link annotation in PDF"
