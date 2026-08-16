"""Iter 66 — AI Tutor ask + Save-as-Flashcard regression suite.

Verifies:
- POST /api/tutor/ask returns < 20s with a grounded answer + citations for course 243
- Vague question returns without 5xx (may have no citations)
- Save-as-flashcard works for own message and rejects a foreign message
- Session flow: list, detail, multi-turn continues in same session
- Timeout guard: normal ask should not 504
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}
ADMIN = {"email": "uat-admin@ifpi.org", "password": "UatAdmin!2026"}
COURSE_ID = 243


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def learner_token():
    return _login(LEARNER)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def learner_h(learner_token):
    return {"Authorization": f"Bearer {learner_token}"}


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── Ask endpoint ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def first_ask(learner_h):
    """Grounded content question — should return quickly with citations."""
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/tutor/ask",
        headers=learner_h,
        json={"question": "What are the functions of the skeletal system?",
              "course_id": COURSE_ID, "top_k": 4},
        timeout=25,
    )
    dt = time.time() - t0
    assert r.status_code == 200, f"ask failed {r.status_code}: {r.text}"
    data = r.json()
    print(f"[first_ask] {dt:.2f}s citations={len(data.get('citations') or [])}")
    return {"elapsed": dt, "data": data}


def test_ask_grounded_returns_answer_with_citations(first_ask):
    d = first_ask["data"]
    assert first_ask["elapsed"] < 20, f"ask took {first_ask['elapsed']:.1f}s"
    assert isinstance(d["answer"], str) and len(d["answer"]) > 20
    assert d["session_id"] and d["message_id"]
    assert isinstance(d["citations"], list)
    assert len(d["citations"]) > 0, "expected citations for course 243"


def test_ask_grounded_not_504(first_ask):
    # Sanity: normal ask must not hit the 60s guard
    assert "took too long" not in first_ask["data"]["answer"].lower()


def test_ask_vague_slide_question_no_5xx(learner_h):
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/tutor/ask",
        headers=learner_h,
        json={"question": "give me more information on this slide",
              "course_id": COURSE_ID, "top_k": 4},
        timeout=25,
    )
    dt = time.time() - t0
    print(f"[vague_ask] {dt:.2f}s status={r.status_code}")
    assert r.status_code < 500, f"vague ask 5xx: {r.status_code} {r.text}"
    assert dt < 20, f"vague ask took {dt:.1f}s"


# ── Session flow ────────────────────────────────────────────────

def test_list_sessions(learner_h, first_ask):
    r = requests.get(f"{BASE_URL}/api/tutor/sessions", headers=learner_h, timeout=10)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["id"] == first_ask["data"]["session_id"] for it in items)


def test_get_session_detail(learner_h, first_ask):
    sid = first_ask["data"]["session_id"]
    r = requests.get(f"{BASE_URL}/api/tutor/sessions/{sid}", headers=learner_h, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == sid
    assert len(body["messages"]) >= 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"


def test_multi_turn_same_session(learner_h, first_ask):
    sid = first_ask["data"]["session_id"]
    r = requests.post(
        f"{BASE_URL}/api/tutor/ask",
        headers=learner_h,
        json={"question": "Give one more example.",
              "course_id": COURSE_ID, "session_id": sid, "top_k": 3},
        timeout=25,
    )
    assert r.status_code == 200, r.text
    assert r.json()["session_id"] == sid


# ── Save-as-flashcard ───────────────────────────────────────────

def test_save_as_flashcard_own_message(learner_h, first_ask):
    mid = first_ask["data"]["message_id"]
    r = requests.post(
        f"{BASE_URL}/api/tutor/save-as-flashcard",
        headers=learner_h,
        json={"message_id": mid, "course_id": COURSE_ID, "difficulty": 2},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("flashcard_id")
    assert body.get("front")
    assert body.get("back_length", 0) > 0


def test_save_as_flashcard_foreign_message_rejected(admin_h, first_ask):
    """Admin (different user) tries to save learner's message_id."""
    mid = first_ask["data"]["message_id"]
    r = requests.post(
        f"{BASE_URL}/api/tutor/save-as-flashcard",
        headers=admin_h,
        json={"message_id": mid, "course_id": COURSE_ID, "difficulty": 2},
        timeout=15,
    )
    # Not owned by admin -> 404
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"
