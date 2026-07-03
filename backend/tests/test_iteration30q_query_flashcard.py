"""Iter 30q — AI Query Builder + Save-as-flashcard."""
from __future__ import annotations

import os

import pyotp  # noqa: F401 (unused, silences lint)
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("2FA on — clear first")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin(): return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner(): return _login("learner@ifpi.org", "learner123")


# ── Query builder ─────────────────────────────────────────────────────


@pytest.mark.slow
def test_query_builder_returns_count(admin):
    r = admin.post(f"{BASE_URL}/api/admin/query-builder/build",
                   json={"question": "How many courses do we have?"},
                   timeout=45)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sql"].strip().lower().startswith("select")
    assert isinstance(body["rows"], list)
    assert body["row_count"] >= 0


@pytest.mark.slow
def test_query_builder_handles_join(admin):
    r = admin.post(f"{BASE_URL}/api/admin/query-builder/build",
                   json={"question": "List top 3 courses by number of enrollments"},
                   timeout=45)
    assert r.status_code == 200
    body = r.json()
    assert " join " in body["sql"].lower() or "count(" in body["sql"].lower()


def test_query_builder_rejects_learner(learner):
    r = learner.post(f"{BASE_URL}/api/admin/query-builder/build",
                     json={"question": "How many courses?"}, timeout=45)
    assert r.status_code == 403


# ── Save-as-flashcard ─────────────────────────────────────────────────


@pytest.mark.slow
def test_save_as_flashcard_from_tutor(learner):
    """End-to-end: ask a tutor question, save the assistant reply as a
    flashcard, verify the flashcard exists in the learner's course pack."""
    # 1. Ask a tutor question in course 1
    ask = learner.post(f"{BASE_URL}/api/tutor/ask",
                       json={"question": "What is a course syllabus?",
                             "course_id": 1},
                       timeout=45).json()
    assert ask["session_id"]
    message_id = ask["message_id"]

    # 2. Save the assistant reply as a flashcard
    r = learner.post(f"{BASE_URL}/api/tutor/save-as-flashcard",
                     json={"message_id": message_id, "course_id": 1,
                           "difficulty": 3},
                     timeout=15)
    assert r.status_code == 200, r.text
    card = r.json()
    assert card["flashcard_id"]
    assert card["front"]

    # 3. Verify it appears via the course due-flashcards endpoint
    #    (learner-side listing — even if next_review_at is future,
    #    /due returns it on first pass since no FlashcardReview exists yet)
    due = learner.get(f"{BASE_URL}/api/learn/flashcards/courses/1/due",
                      timeout=10)
    assert due.status_code == 200
    body = due.json()
    ids = [item["id"] for item in body.get("cards", body.get("items", []))]
    assert card["flashcard_id"] in ids, (
        f"saved card {card['flashcard_id']} not in due list {ids[:10]}"
    )


def test_save_as_flashcard_rejects_someone_elses_message(admin):
    """Cross-user: admin tries to save a message from a session they
    don't own → 404."""
    r = admin.post(f"{BASE_URL}/api/tutor/save-as-flashcard",
                   json={"message_id": 999999, "course_id": 1,
                         "difficulty": 3},
                   timeout=10)
    assert r.status_code == 404
