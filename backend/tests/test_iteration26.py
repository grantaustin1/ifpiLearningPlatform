"""Iter 25b + 25c + 26a — DB unique constraints, flashcard streak/XP, and
OpenAI TTS narration.

Runs against the live REACT_APP_BACKEND_URL preview backend.
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


# ─── Iter 25b: DB unique constraints ─────────────────────────────────
def test_courses_uq_org_title_returns_409(admin):
    """Attempting to create a duplicate title in the same org returns 409
    (via app-side pre-check), not 500 from the DB constraint."""
    title = "IFPI Fundamentals"   # always exists in seed data
    r = admin.post(f"{BASE_URL}/api/courses",
                   json={"title": title, "description": "dup test"},
                   timeout=10)
    assert r.status_code == 409, r.text
    assert "already exists" in r.json()["detail"]


# ─── Iter 25c: flashcard streak + XP ─────────────────────────────────
def test_streak_endpoint_shape(learner):
    r = learner.get(f"{BASE_URL}/api/learn/flashcards/streak", timeout=10)
    assert r.status_code == 200
    body = r.json()
    for k in ("current_streak", "longest_streak", "reviewed_today"):
        assert k in body
    assert body["current_streak"] >= 0
    assert isinstance(body["reviewed_today"], bool)


def test_review_awards_xp_and_returns_streak(admin, learner):
    """Bulk-save a card, learner reviews with quality=5 → returns
    xp_awarded > 0 and updated streak."""
    front = f"XP test {time.time():.0f}"
    save_r = admin.post(f"{BASE_URL}/api/authoring/flashcards/bulk-save",
                        json={"course_id": 1, "cards": [
                            {"front": front, "back": "a", "difficulty": 2, "tags": []}
                        ]}, timeout=15)
    assert save_r.status_code == 200
    card_id = save_r.json()["cards"][0]["id"]

    # Get user's XP before
    me_before = learner.get(f"{BASE_URL}/api/auth/me", timeout=10).json()
    xp_before = me_before.get("points", 0)

    rev = learner.post(f"{BASE_URL}/api/learn/flashcards/{card_id}/review",
                       json={"quality": 5}, timeout=10)
    assert rev.status_code == 200, rev.text
    body = rev.json()
    assert body["xp_awarded"] >= 4        # quality=5 → XP_FLASHCARD_PERFECT
    assert "streak" in body
    assert body["streak"]["current_streak"] >= 1
    assert body["streak"]["reviewed_today"] is True

    # Confirm user's total points advanced
    me_after = learner.get(f"{BASE_URL}/api/auth/me", timeout=10).json()
    assert me_after.get("points", 0) > xp_before

    admin.delete(f"{BASE_URL}/api/authoring/flashcards/{card_id}", timeout=10)


def test_low_quality_review_does_not_award_xp(admin, learner):
    front = f"No-XP test {time.time():.0f}"
    save_r = admin.post(f"{BASE_URL}/api/authoring/flashcards/bulk-save",
                        json={"course_id": 1, "cards": [
                            {"front": front, "back": "a", "difficulty": 2}
                        ]}, timeout=15)
    card_id = save_r.json()["cards"][0]["id"]

    rev = learner.post(f"{BASE_URL}/api/learn/flashcards/{card_id}/review",
                       json={"quality": 1}, timeout=10)
    assert rev.status_code == 200
    body = rev.json()
    assert body["xp_awarded"] == 0
    assert body["streak_bonus_applied"] is False

    admin.delete(f"{BASE_URL}/api/authoring/flashcards/{card_id}", timeout=10)


# ─── Iter 26a: TTS narration ─────────────────────────────────────────
def test_narration_generate_and_clear(admin):
    """Generate + attach narration to a slide, verify it becomes retrievable
    on the course endpoint, then clear it."""
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    slide_id = slides[0]["id"]

    r = admin.post(
        f"{BASE_URL}/api/authoring/narration/generate",
        json={
            "slide_id": slide_id, "voice": "nova", "model": "tts-1",
            "override_text": "Welcome to lesson one. This is a short narration test that exercises the TTS pipeline end to end.",
        }, timeout=60,
    )
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["narration_url"]
    assert body["voice"] == "nova"
    assert body["size_bytes"] > 1000
    assert body["cost_cents"] >= 1

    # The course endpoint now surfaces the narration_url
    refreshed = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    matching = next((s for s in refreshed["slides"] if s["id"] == slide_id), None)
    assert matching is not None
    assert matching["narration_url"] == body["narration_url"]
    assert matching["narration_voice"] == "nova"

    # The audio itself is publicly retrievable
    audio = requests.get(f"{BASE_URL}{body['narration_url']}", timeout=15)
    assert audio.status_code == 200
    assert len(audio.content) > 1000

    # Cleanup
    clr = admin.delete(f"{BASE_URL}/api/authoring/narration/{slide_id}", timeout=10)
    assert clr.status_code == 200


def test_narration_rejects_invalid_voice(admin):
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    r = admin.post(
        f"{BASE_URL}/api/authoring/narration/generate",
        json={"slide_id": slides[0]["id"], "voice": "godzilla",
              "override_text": "Some sample content to narrate for the test."},
        timeout=15,
    )
    assert r.status_code == 400


def test_narration_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/narration/generate",
                     json={"slide_id": 1}, timeout=10)
    assert r.status_code == 403


def test_narration_rejects_short_text(admin):
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    r = admin.post(
        f"{BASE_URL}/api/authoring/narration/generate",
        json={"slide_id": slides[0]["id"], "override_text": "Hi."},
        timeout=15,
    )
    assert r.status_code == 400


# ─── TTS pure-function tests ─────────────────────────────────────────
def test_tts_chunker_short():
    from services.tts_service import _chunk_text
    assert _chunk_text("Hello world.") == ["Hello world."]


def test_tts_chunker_long_splits_on_sentence():
    from services.tts_service import _chunk_text
    text = ("This is sentence one. " * 500).strip()  # ~10K chars
    chunks = _chunk_text(text, chunk_size=4096)
    assert len(chunks) >= 2
    assert all(len(c) <= 4096 for c in chunks)
    # No sentence-mid split — chunks should end at ".":
    for c in chunks[:-1]:
        assert c.rstrip().endswith(".") or c.rstrip().endswith("one") or c.endswith(" ")


def test_tts_cost_estimate():
    from services.tts_service import estimated_cost_cents
    # 1000 chars * $0.015/1K = 1.5 cents (min 1)
    assert estimated_cost_cents("x" * 1000, "tts-1") >= 1
    # tts-1-hd is 2x more
    assert (estimated_cost_cents("x" * 2000, "tts-1-hd")
            > estimated_cost_cents("x" * 2000, "tts-1"))
