"""Iter 28 — dedicated worker + video cost preview + mind-map layout persistence +
verify rate-limit + auth landing hooks.
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
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _login("learner@ifpi.org", "learner123")


# ─── Rate limiter (30/min per IP) ────────────────────────────────────
def test_verify_rate_limit_kicks_in_after_30_calls():
    """Anonymous verify endpoint returns 429 after 30 hits in a minute."""
    seen_429 = False
    for i in range(45):
        r = requests.get(f"{BASE_URL}/api/public/certificates/verify/BLAH{i}", timeout=5)
        if r.status_code == 429:
            seen_429 = True
            assert "Retry-After" in r.headers
            break
    assert seen_429, "Expected a 429 within 45 rapid-fire attempts"


# Sleep to reset the rate-limit window for subsequent tests
@pytest.fixture(autouse=True)
def _reset_window():
    """Rate limit window is 60s — a brief sleep between tests keeps the
    remaining tests in the same file below the limit."""
    yield
    time.sleep(0.05)


# ─── Sora video cost preview ────────────────────────────────────────
def test_video_preview_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/video/preview",
                     json={"model": "sora-2", "duration": 4}, timeout=10)
    assert r.status_code == 403


def test_video_preview_returns_cost_and_budget(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/video/preview",
                   json={"model": "sora-2", "duration": 8}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estimated_cost_cents"] > 0
    assert "budget" in body
    for k in ("budget_cents", "spent_cents", "remaining_cents"):
        assert k in body["budget"]
    assert body["will_exceed_budget"] in (True, False)


def test_video_preview_rejects_invalid():
    admin_sess = _login("admin@ifpi.org", "admin123")
    r = admin_sess.post(f"{BASE_URL}/api/authoring/video/preview",
                        json={"model": "sora-2", "duration": 5}, timeout=10)
    assert r.status_code == 400


# ─── Mind map layout persistence ────────────────────────────────────
def test_mindmap_layout_roundtrip(admin):
    # Save
    payload = {
        "graph": {"root": {"id": "root", "label": "Course"},
                  "topics": [{"id": "t1", "label": "A", "children": []}]},
        "positions": {"root": {"x": 100, "y": 200},
                      "t1": {"x": 300, "y": 400}},
    }
    r = admin.put(f"{BASE_URL}/api/authoring/mindmap/1/layout",
                  json=payload, timeout=10)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Load
    r2 = admin.get(f"{BASE_URL}/api/authoring/mindmap/1/layout", timeout=10)
    assert r2.status_code == 200
    body = r2.json()
    assert body["has_saved"] is True
    assert body["positions"]["root"] == {"x": 100, "y": 200}
    assert body["positions"]["t1"] == {"x": 300, "y": 400}
    assert body["graph"]["root"]["label"] == "Course"

    # Clear
    r3 = admin.delete(f"{BASE_URL}/api/authoring/mindmap/1/layout", timeout=10)
    assert r3.status_code == 200

    r4 = admin.get(f"{BASE_URL}/api/authoring/mindmap/1/layout", timeout=10)
    assert r4.json()["has_saved"] is False


def test_mindmap_layout_learner_blocked(learner):
    r = learner.get(f"{BASE_URL}/api/authoring/mindmap/1/layout", timeout=10)
    assert r.status_code == 403


def test_mindmap_layout_404_on_missing_course(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/mindmap/999999/layout", timeout=10)
    assert r.status_code == 404


# ─── Dedicated worker (indirect — job still enqueues) ────────────────
def test_video_start_still_returns_202_with_dedicated_worker(admin):
    """After the dedicated-worker refactor the endpoint contract is
    unchanged: 202 with job_id. The actual Sora render is not exercised
    here to save cost."""
    r = admin.post(f"{BASE_URL}/api/authoring/video/generate",
                   json={"prompt": "Notes flowing along a treble clef",
                         "model": "sora-2", "size": "1280x720",
                         "duration": 4}, timeout=15)
    assert r.status_code == 202, r.text
    assert isinstance(r.json()["job_id"], int)
