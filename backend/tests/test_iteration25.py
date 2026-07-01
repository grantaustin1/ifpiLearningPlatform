"""Iter 25 — Flashcards + SM-2 spaced-repetition tests.

Uses the live backend behind REACT_APP_BACKEND_URL — same pattern as the
other test_iteration*.py files.
"""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _login("learner@ifpi.org", "learner123")


# ─── SM-2 pure algorithm ─────────────────────────────────────────────
def test_sm2_correct_answer_progresses_interval():
    from services.flashcard_service import apply_sm2
    ef, iv, reps, _ = apply_sm2(quality=5, ease=2.5, interval_days=0, repetitions=0)
    assert reps == 1 and iv == 1 and ef > 2.5


def test_sm2_second_correct_review_is_six_days():
    from services.flashcard_service import apply_sm2
    ef, iv, reps, _ = apply_sm2(quality=4, ease=2.5, interval_days=1, repetitions=1)
    assert reps == 2 and iv == 6


def test_sm2_third_correct_multiplies_by_ease():
    from services.flashcard_service import apply_sm2
    _, iv, reps, _ = apply_sm2(quality=5, ease=2.6, interval_days=6, repetitions=2)
    # 6 * 2.6 = 15.6 → rounds to 16
    assert reps == 3 and iv == 16


def test_sm2_wrong_answer_resets_repetitions():
    from services.flashcard_service import apply_sm2
    ef, iv, reps, _ = apply_sm2(quality=1, ease=2.5, interval_days=30, repetitions=4)
    assert reps == 0 and iv == 1 and ef < 2.5


def test_sm2_ease_floor_is_1_3():
    from services.flashcard_service import apply_sm2
    ef, _, _, _ = apply_sm2(quality=0, ease=1.4, interval_days=1, repetitions=1)
    assert ef == 1.3


# ─── Authoring: staff-only endpoints ────────────────────────────────
def test_learner_cannot_authoring_generate(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/flashcards/generate",
                     json={"course_id": 1, "count": 3}, timeout=10)
    assert r.status_code == 403


def test_learner_cannot_bulk_save(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/flashcards/bulk-save",
                     json={"course_id": 1, "cards": []}, timeout=10)
    assert r.status_code == 403


def test_admin_can_list_flashcards_by_course(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/flashcards/by-course/1", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body


def test_bulk_save_and_learner_review_flow(admin, learner):
    """End-to-end: staff bulk-saves a card, learner sees it in `due`,
    submits a review, and it disappears from the due queue (next_review
    scheduled 1 day out)."""
    front = f"E2E test card {time.time():.0f}"
    save_r = admin.post(f"{BASE_URL}/api/authoring/flashcards/bulk-save",
                        json={"course_id": 1, "cards": [
                            {"front": front, "back": "answer body",
                             "difficulty": 2, "tags": ["test"]}
                        ]}, timeout=15)
    assert save_r.status_code == 200
    card_id = save_r.json()["cards"][0]["id"]

    # Learner sees it as "new" in due queue
    due = learner.get(f"{BASE_URL}/api/learn/flashcards/courses/1/due", timeout=10)
    assert due.status_code == 200
    dj = due.json()
    ids = [c["id"] for c in dj["cards"]]
    assert card_id in ids

    # Learner reviews with quality=5
    rev = learner.post(f"{BASE_URL}/api/learn/flashcards/{card_id}/review",
                       json={"quality": 5}, timeout=10)
    assert rev.status_code == 200
    review = rev.json()["review"]
    assert review["interval_days"] == 1
    assert review["repetitions"] == 1

    # Now it should no longer be "due" (scheduled 1 day out)
    due2 = learner.get(f"{BASE_URL}/api/learn/flashcards/courses/1/due", timeout=10)
    ids2 = [c["id"] for c in due2.json()["cards"]]
    assert card_id not in ids2

    # Cleanup
    admin.delete(f"{BASE_URL}/api/authoring/flashcards/{card_id}", timeout=10)


def test_stats_endpoint(learner):
    r = learner.get(f"{BASE_URL}/api/learn/flashcards/courses/1/stats", timeout=10)
    assert r.status_code == 200
    s = r.json()
    for k in ("total", "new", "learning", "mastered", "due_now"):
        assert k in s


def test_admin_generate_returns_valid_shape(admin):
    """Only exercises the endpoint contract — real generation depends on
    Emergent LLM key + tiny slide set. Skipped gracefully if no LLM key."""
    r = admin.post(f"{BASE_URL}/api/authoring/flashcards/generate",
                   json={"course_id": 1, "count": 2, "use_sources": False},
                   timeout=60)
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("cards"), list)
    for c in body["cards"]:
        assert c["front"] and c["back"]
        assert 1 <= c["difficulty"] <= 5
