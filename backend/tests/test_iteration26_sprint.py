"""Iter 26 Sprint — Slide-level drop-off analytics + Learner "My RSVPs" ICS
feed + Rate-limit env-fix + Learning streak endpoint.

Runs against the live REACT_APP_BACKEND_URL preview backend.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping", allow_module_level=True)

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    r.raise_for_status()
    tok = r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def learner():
    return _login(LEARNER)


# ── Course & slide fixture ───────────────────────────────────────────
@pytest.fixture(scope="module")
def course_with_slides(admin):
    """Create a small published course with 3 slides. Cleans up after."""
    r = admin.post(f"{BASE_URL}/api/courses",
                   json={"title": f"TEST_iter26sprint_{uuid.uuid4().hex[:8]}",
                         "description": "iter26 dropoff harness"},
                   timeout=10)
    assert r.status_code in (200, 201), r.text
    course = r.json()
    slide_ids = []
    for i in range(3):
        rs = admin.post(f"{BASE_URL}/api/courses/{course['id']}/slides",
                        json={"title": f"Slide {i+1}", "content": f"body {i+1}",
                              "slide_type": "TEXT"}, timeout=10)
        assert rs.status_code in (200, 201), rs.text
        slide_ids.append(rs.json()["id"])
    admin.patch(f"{BASE_URL}/api/courses/{course['id']}",
                json={"status": "PUBLISHED"}, timeout=10)
    yield {"course": course, "slide_ids": slide_ids}
    try:
        admin.delete(f"{BASE_URL}/api/courses/{course['id']}", timeout=10)
    except Exception:
        pass


# ── Slide drop-off ───────────────────────────────────────────────────
def test_track_slide_view_records_impression(learner, course_with_slides):
    cid = course_with_slides["course"]["id"]
    sid = course_with_slides["slide_ids"][0]
    r = learner.post(f"{BASE_URL}/api/catalog/{cid}/slides/{sid}/track-view",
                     timeout=10)
    assert r.status_code == 200, r.text
    assert r.json().get("tracked") is True
    r2 = learner.post(f"{BASE_URL}/api/catalog/{cid}/slides/{sid}/track-view",
                      timeout=10)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get("tracked") is False
    assert body2.get("reason") == "already_counted_today"


def test_track_slide_view_rejects_unknown_slide(learner, course_with_slides):
    cid = course_with_slides["course"]["id"]
    r = learner.post(f"{BASE_URL}/api/catalog/{cid}/slides/999999999/track-view",
                     timeout=10)
    assert r.status_code == 200
    assert r.json().get("reason") == "unknown_slide"


def test_course_dropoff_endpoint_shape(admin, learner, course_with_slides):
    cid = course_with_slides["course"]["id"]
    slides = course_with_slides["slide_ids"]
    # Ensure at least first slide has a view
    learner.post(f"{BASE_URL}/api/catalog/{cid}/slides/{slides[0]}/track-view",
                 timeout=10)
    r = admin.get(f"{BASE_URL}/api/admin/course-dropoff/{cid}", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["course_id"] == cid
    assert body["baseline_viewers"] >= 1
    assert len(body["slides"]) == 3
    assert body["slides"][0]["retention"] == 1.0
    assert body["slides"][1]["unique_viewers"] == 0
    assert body["slides"][2]["unique_viewers"] == 0
    # step_dropoff is 100% between slide 1 and 2 in this scenario
    assert body["slides"][1]["step_dropoff"] == 1.0


def test_course_dropoff_requires_staff(learner, course_with_slides):
    cid = course_with_slides["course"]["id"]
    r = learner.get(f"{BASE_URL}/api/admin/course-dropoff/{cid}", timeout=10)
    assert r.status_code == 403


# ── My RSVPs ICS feed ────────────────────────────────────────────────
def test_subscribe_url_accepts_my_rsvps_kind(learner):
    r = learner.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=my_rsvps",
                     timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body
    assert body["path"].endswith(".ics")
    r2 = requests.get(f"{BASE_URL}{body['path']}", timeout=10)
    assert r2.status_code == 200
    assert r2.headers["Content-Type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in r2.text


def test_subscribe_url_my_rsvps_contains_only_rsvped(admin, learner):
    tag = uuid.uuid4().hex[:8]
    base_dt = datetime.now(timezone.utc) + timedelta(days=3)

    def _mk(title, start):
        payload = {
            "title": title,
            "meeting_url": "https://zoom.us/j/test123",
            "start_at": start.isoformat().replace("+00:00", "Z"),
            "duration_minutes": 30,
        }
        r = admin.post(f"{BASE_URL}/api/live-sessions", json=payload, timeout=10)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    rsvp_id = _mk(f"TEST_iter26_rsvp_{tag}", base_dt)
    skip_id = _mk(f"TEST_iter26_skip_{tag}", base_dt + timedelta(days=1))
    try:
        r = learner.post(f"{BASE_URL}/api/live-sessions/{rsvp_id}/rsvp", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "RSVP"
        r = learner.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=my_rsvps",
                         timeout=10)
        assert r.status_code == 200
        ics_url = r.json()["path"]
        r2 = requests.get(f"{BASE_URL}{ics_url}", timeout=10)
        assert r2.status_code == 200
        text = r2.text
        assert f"live-session-{rsvp_id}@ifpi.org" in text, "RSVP'd should be present"
        assert f"live-session-{skip_id}@ifpi.org" not in text, "non-RSVP'd must NOT appear"
    finally:
        admin.delete(f"{BASE_URL}/api/live-sessions/{rsvp_id}", timeout=10)
        admin.delete(f"{BASE_URL}/api/live-sessions/{skip_id}", timeout=10)


def test_qr_endpoint_accepts_my_rsvps_kind(learner):
    r = learner.get(f"{BASE_URL}/api/live-sessions/subscribe-url/qr",
                    params={"kind": "my_rsvps"}, timeout=10)
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("image/svg+xml")
    assert r.content.startswith(b"<?xml") or r.content.startswith(b"<svg")


# ── Rate-limit env-fix ───────────────────────────────────────────────
def test_rate_limit_test_client_ip_pins_bucket(learner):
    """Two distinct pinned IPs each get their own 30-req window. IP-B
    stays clean while IP-A is fully throttled."""
    try:
        import redis
        redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0")).flushdb()
    except Exception:
        pass

    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    code = (certs[0].get("code") or certs[0].get("cert_code")) if certs else "BOGUS-CODE"

    ip_a = f"10.99.{uuid.uuid4().int % 200 + 1}.5"
    ip_b = f"10.99.{(uuid.uuid4().int % 200) + 1}.99"

    saw_429_a = False
    for _ in range(60):
        r = requests.get(f"{BASE_URL}/api/public/certificates/verify/{code}",
                         headers={"X-Test-Client-Ip": ip_a}, timeout=10)
        if r.status_code == 429:
            saw_429_a = True
            break
    assert saw_429_a, "IP-A must be throttled within 60 rapid-fire requests"

    good_b = 0
    for _ in range(5):
        r = requests.get(f"{BASE_URL}/api/public/certificates/verify/{code}",
                         headers={"X-Test-Client-Ip": ip_b}, timeout=10)
        if r.status_code in (200, 404):
            good_b += 1
    assert good_b >= 3, f"IP-B should be unaffected, got {good_b}/5 non-429"


# ── Learning streak ─────────────────────────────────────────────────
def test_learning_streak_endpoint_shape(learner):
    r = learner.get(f"{BASE_URL}/api/gamification/learning-streak", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("current_streak", "longest_streak", "active_today", "last_active_date"):
        assert key in body
    assert isinstance(body["current_streak"], int)
    assert isinstance(body["longest_streak"], int)
    assert isinstance(body["active_today"], bool)


def test_learning_streak_reflects_slide_view(learner, course_with_slides):
    cid = course_with_slides["course"]["id"]
    sid = course_with_slides["slide_ids"][0]
    learner.post(f"{BASE_URL}/api/catalog/{cid}/slides/{sid}/track-view", timeout=10)
    r = learner.get(f"{BASE_URL}/api/gamification/learning-streak", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["active_today"] is True
    assert body["current_streak"] >= 1
