"""Iter 26b + 27a — Sora 2 video overviews + Nano Banana infographics.

Video generation takes 2-6 minutes — we assert the job STARTS and moves
into PENDING/RUNNING quickly. A separate slow test can wait for COMPLETED.
Nano Banana is sync (~10s) so we can fully exercise the round trip.
"""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    import pytest
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests", allow_module_level=True)


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


# ─── Sora video — auth gates + validation ───────────────────────────
def test_video_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/video/generate",
                     json={"prompt": "some safe prompt"}, timeout=10)
    assert r.status_code == 403


def test_video_invalid_size_rejected(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/video/generate",
                   json={"prompt": "a decent-length prompt for tests",
                         "size": "640x480"}, timeout=15)
    assert r.status_code == 400


def test_video_invalid_duration_rejected(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/video/generate",
                   json={"prompt": "a decent-length prompt for tests",
                         "duration": 5}, timeout=15)
    assert r.status_code == 400


def test_video_invalid_model_rejected(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/video/generate",
                   json={"prompt": "a decent-length prompt for tests",
                         "model": "sora-1"}, timeout=15)
    assert r.status_code == 400


def test_video_start_returns_202_with_job_id(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/video/generate",
                   json={"prompt": "Musical notes flowing along a staff",
                         "model": "sora-2", "size": "1280x720",
                         "duration": 4}, timeout=15)
    assert r.status_code == 202, r.text
    body = r.json()
    assert isinstance(body["job_id"], int)
    assert body["status"] in ("PENDING", "RUNNING")
    assert body["estimated_cost_cents"] > 0


def test_video_history_lists_started_job(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/video/history", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    # We started at least one job in this session
    assert any(j["job_type"] == "SORA_VIDEO" for j in body["items"])


# ─── Sora cost estimator (pure) ─────────────────────────────────────
def test_video_cost_scales_with_model_and_duration():
    from services.video_service import estimated_cost_cents
    assert estimated_cost_cents("sora-2", 4) < estimated_cost_cents("sora-2", 12)
    assert estimated_cost_cents("sora-2", 12) < estimated_cost_cents("sora-2-pro", 12)
    assert estimated_cost_cents("sora-2", 4) >= 1


# ─── Nano Banana infographic ─────────────────────────────────────────
def test_visuals_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/visuals/generate",
                     json={"prompt": "some safe prompt"}, timeout=10)
    assert r.status_code == 403


def test_visuals_prompt_too_short_rejected(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/visuals/generate",
                   json={"prompt": "hi"}, timeout=15)
    assert r.status_code == 422    # pydantic min_length


def test_visuals_generate_returns_image_url(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/visuals/generate",
                   json={"prompt": "Simple diagram showing three phases: A, B, C",
                         "attach_to_slide": False}, timeout=90)
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set or gemini image not available")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"].startswith("/api/uploads/")
    assert body["size_bytes"] > 5000
    assert body["cost_cents"] >= 1
    assert body["attached"] is False

    # The PNG/JPG is retrievable
    img = requests.get(f"{BASE_URL}{body['url']}", timeout=15)
    assert img.status_code == 200
    assert len(img.content) == body["size_bytes"]


def test_visuals_attach_to_slide_updates_media_url(admin):
    """attach_to_slide=True + slide_id → slide.media_url gets updated."""
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    slide_id = slides[0]["id"]

    r = admin.post(f"{BASE_URL}/api/authoring/visuals/generate",
                   json={"prompt": "A minimalist icon showing an equalizer bar chart",
                         "slide_id": slide_id, "attach_to_slide": True},
                   timeout=90)
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attached"] is True
    assert body["slide_id"] == slide_id

    refreshed = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    match = next((s for s in refreshed["slides"] if s["id"] == slide_id), None)
    assert match is not None
    assert match["media_url"] == body["url"]
    assert match["slide_type"] == "IMAGE"


def test_visuals_cost_estimate():
    from services.visuals_service import estimated_cost_cents
    assert estimated_cost_cents("gemini-3.1-flash-image-preview") >= 1
    assert (estimated_cost_cents("gemini-3-pro-image-preview")
            > estimated_cost_cents("gemini-3.1-flash-image-preview"))
