"""Iter 22 — Live Sessions module tests.

Covers admin create/list/patch/delete, learner RSVP toggle, admin mark-
attendance bulk endpoint, `/upcoming` cohort filtering, ICS export, and
authorisation (learner cannot create/mark-attendance).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    r.raise_for_status()
    tok = r.json().get("access_token")
    s = requests.Session()
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def learner():
    return _login(LEARNER)


@pytest.fixture()
def session_id(admin):
    """Create a fresh session and clean it up after the test."""
    start = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "Iter22 test cohort call",
        "description": "Weekly sync",
        "meeting_url": "https://meet.example.com/xyz",
        "start_at": start,
        "duration_minutes": 45,
        "host_name": "Test Host",
    }, timeout=15)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    yield sid
    # cleanup — DELETE returns 204
    admin.delete(f"{BASE_URL}/api/live-sessions/{sid}", timeout=10)


# ── Create / list / detail ───────────────────────────────────────────
def test_admin_can_create_session(admin, session_id):
    r = admin.get(f"{BASE_URL}/api/live-sessions/{session_id}", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "Iter22 test cohort call"
    assert d["duration_minutes"] == 45
    assert d["host_name"] == "Test Host"
    assert d["rsvp_count"] == 0
    assert d["attendance_count"] == 0
    assert isinstance(d["rsvps"], list)


def test_list_sessions_returns_created_row(admin, session_id):
    r = admin.get(f"{BASE_URL}/api/live-sessions", timeout=10)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["sessions"]]
    assert session_id in ids


def test_patch_session_updates_fields(admin, session_id):
    r = admin.patch(f"{BASE_URL}/api/live-sessions/{session_id}",
                    json={"title": "renamed", "duration_minutes": 90}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "renamed"
    assert d["duration_minutes"] == 90


# ── RSVP ─────────────────────────────────────────────────────────────
def test_learner_can_rsvp_and_cancel(admin, learner, session_id):
    r = learner.post(f"{BASE_URL}/api/live-sessions/{session_id}/rsvp", timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "RSVP"
    # Toggle again → CANCELLED
    r2 = learner.post(f"{BASE_URL}/api/live-sessions/{session_id}/rsvp", timeout=10)
    assert r2.status_code == 200 and r2.json()["status"] == "CANCELLED"
    # Detail counts should exclude CANCELLED
    d = admin.get(f"{BASE_URL}/api/live-sessions/{session_id}", timeout=10).json()
    assert d["rsvp_count"] == 0


# ── Mark attendance ──────────────────────────────────────────────────
def test_admin_can_bulk_mark_attendance(admin, learner, session_id):
    # Learner RSVPs first
    learner.post(f"{BASE_URL}/api/live-sessions/{session_id}/rsvp", timeout=10)
    # Look up learner user_id from /api/auth/me
    me = learner.get(f"{BASE_URL}/api/auth/me", timeout=10).json()
    r = admin.post(f"{BASE_URL}/api/live-sessions/{session_id}/mark-attendance",
                   json={"user_ids": [me["id"]], "status": "ATTENDED"}, timeout=10)
    assert r.status_code == 200 and r.json()["marked"] == 1
    d = admin.get(f"{BASE_URL}/api/live-sessions/{session_id}", timeout=10).json()
    assert d["attendance_count"] == 1


def test_learner_cannot_mark_attendance(learner, session_id):
    r = learner.post(f"{BASE_URL}/api/live-sessions/{session_id}/mark-attendance",
                     json={"user_ids": [1], "status": "ATTENDED"}, timeout=10)
    assert r.status_code in (401, 403)


# ── /upcoming ────────────────────────────────────────────────────────
def test_learner_upcoming_endpoint_returns_session(learner, session_id):
    r = learner.get(f"{BASE_URL}/api/live-sessions/upcoming", timeout=10)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["sessions"]]
    assert session_id in ids


# ── Cohort filtering ─────────────────────────────────────────────────
def test_cohort_restricted_session_hidden_from_non_cohort_learner(admin, learner):
    start = (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "Cohort-only session", "meeting_url": "https://zoom.us/j/1",
        "start_at": start, "duration_minutes": 30, "cohort": "does-not-exist-cohort-xyz",
    }, timeout=10)
    assert r.status_code == 201
    sid = r.json()["id"]
    try:
        up = learner.get(f"{BASE_URL}/api/live-sessions/upcoming", timeout=10).json()
        ids = [s["id"] for s in up["sessions"]]
        assert sid not in ids, "cohort-mismatched learner should not see the session"
    finally:
        admin.delete(f"{BASE_URL}/api/live-sessions/{sid}", timeout=10)


# ── ICS export ───────────────────────────────────────────────────────
def test_ics_download_valid_calendar(admin, session_id):
    r = admin.get(f"{BASE_URL}/api/live-sessions/{session_id}/ics", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "BEGIN:VEVENT" in body and "END:VEVENT" in body
    assert body.rstrip().endswith("END:VCALENDAR")
    assert "SUMMARY:" in body and "DTSTART:" in body
    assert r.headers["content-type"].startswith("text/calendar")


# ── Auth guardrails ─────────────────────────────────────────────────
def test_learner_cannot_create_session(learner):
    r = learner.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "hack",
        "meeting_url": "https://zoom.us/j/x",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }, timeout=10)
    assert r.status_code in (401, 403)


def test_delete_returns_204(admin):
    start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "delete-me", "meeting_url": "https://zoom.us/j/2",
        "start_at": start,
    }, timeout=10)
    sid = r.json()["id"]
    d = admin.delete(f"{BASE_URL}/api/live-sessions/{sid}", timeout=10)
    assert d.status_code == 204
    g = admin.get(f"{BASE_URL}/api/live-sessions/{sid}", timeout=10)
    assert g.status_code == 404
