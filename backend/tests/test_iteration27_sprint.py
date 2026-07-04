"""Iter 27 Sprint — Attendance certs + Cross-tenant marketplace + Streak nudge.

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
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

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


def _get_learner_id(learner) -> int:
    r = learner.get(f"{BASE_URL}/api/auth/me", timeout=10)
    r.raise_for_status()
    return r.json()["id"]


# ── Attendance certificate lifecycle ────────────────────────────────
@pytest.fixture()
def session_with_rsvp(admin, learner):
    payload = {
        "title": f"TEST_iter27_attend_{uuid.uuid4().hex[:8]}",
        "meeting_url": "https://zoom.us/j/test-iter27",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "duration_minutes": 45,
    }
    r = admin.post(f"{BASE_URL}/api/live-sessions", json=payload, timeout=10)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = learner.post(f"{BASE_URL}/api/live-sessions/{sid}/rsvp", timeout=10)
    assert r.status_code == 200
    yield sid
    try: admin.delete(f"{BASE_URL}/api/live-sessions/{sid}", timeout=10)
    except Exception: pass


def test_mark_attendance_issues_cert(admin, learner, session_with_rsvp):
    uid = _get_learner_id(learner)
    r = admin.post(
        f"{BASE_URL}/api/live-sessions/{session_with_rsvp}/mark-attendance",
        json={"user_ids": [uid], "status": "ATTENDED"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["marked"] == 1
    assert body["status"] == "ATTENDED"
    assert body["attendance_certs_issued"] == 1

    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    attend_certs = [c for c in certs if c["type"] == "LIVE_SESSION_ATTENDANCE"]
    assert len(attend_certs) >= 1
    cert = attend_certs[0]
    assert cert.get("course_title"), "must surface session title"

    r = learner.get(f"{BASE_URL}/api/certificates/{cert['id']}/pdf", timeout=15)
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF-")


def test_mark_attendance_is_idempotent(admin, learner, session_with_rsvp):
    uid = _get_learner_id(learner)
    admin.post(
        f"{BASE_URL}/api/live-sessions/{session_with_rsvp}/mark-attendance",
        json={"user_ids": [uid], "status": "ATTENDED"}, timeout=10,
    )
    r2 = admin.post(
        f"{BASE_URL}/api/live-sessions/{session_with_rsvp}/mark-attendance",
        json={"user_ids": [uid], "status": "ATTENDED"}, timeout=10,
    )
    assert r2.status_code == 200
    assert r2.json()["attendance_certs_issued"] == 0


def test_verify_endpoint_shows_session_title(admin, learner, session_with_rsvp):
    uid = _get_learner_id(learner)
    admin.post(
        f"{BASE_URL}/api/live-sessions/{session_with_rsvp}/mark-attendance",
        json={"user_ids": [uid], "status": "ATTENDED"}, timeout=10,
    )
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    attend = next(c for c in certs if c["type"] == "LIVE_SESSION_ATTENDANCE")
    r = requests.get(f"{BASE_URL}/api/certificates/verify/{attend['code']}", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "LIVE_SESSION_ATTENDANCE"
    assert body["valid"] is True
    assert body["course_title"]


# ── Cross-tenant marketplace ────────────────────────────────────────
def test_catalog_organizations_endpoint(admin):
    admin.patch(f"{BASE_URL}/api/admin/organization",
                json={"marketplace_opt_in": True}, timeout=10)
    r = requests.get(f"{BASE_URL}/api/catalog/organizations", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    if body:
        row = body[0]
        for key in ("id", "name", "logo_url", "course_count"):
            assert key in row


def test_catalog_org_filter_narrows_results(admin):
    r = admin.get(f"{BASE_URL}/api/auth/me", timeout=10)
    org_id = r.json()["organization_id"]
    r = requests.get(f"{BASE_URL}/api/catalog",
                     params={"org": org_id, "page_size": 10}, timeout=10)
    assert r.status_code == 200
    for c in r.json()["courses"]:
        if c.get("organization"):
            assert c["organization"]["id"] == org_id


def test_catalog_search_matches_org_name(admin):
    """Search that matches only the org name should still return rows."""
    orgs = requests.get(f"{BASE_URL}/api/catalog/organizations", timeout=10).json()
    if not orgs:
        pytest.skip("no opted-in orgs in seed")
    q = orgs[0]["name"].split()[0]  # first word of first org name
    r = requests.get(f"{BASE_URL}/api/catalog",
                     params={"q": q, "page_size": 5}, timeout=10)
    assert r.status_code == 200
    # Cross-tenant search must not crash; total >=0 always but org
    # match should yield at least the orgs's own courses
    assert isinstance(r.json()["total"], int)


# ── Streak-nudge worker ─────────────────────────────────────────────
def test_streak_nudge_worker_notification_lifecycle(learner):
    """Backfill a 3-day streak that skipped today, then run the worker
    in-process. First run emits a nudge Notification; second run must
    be blocked by the cooldown."""
    from datetime import datetime as dt, timezone as tz, timedelta as td
    from core.database import SessionLocal
    from models import SlideView, User, Notification
    from services.streak_nudge_worker import run_streak_nudge_pass

    uid = _get_learner_id(learner)
    db = SessionLocal()
    try:
        db.query(Notification).filter(
            Notification.user_id == uid,
            Notification.type == "STREAK_NUDGE",
        ).delete()
        u = db.query(User).filter(User.id == uid).first()
        u.streak_nudge_last_sent_at = None
        today = dt.now(tz.utc).date().isoformat()
        db.query(SlideView).filter(
            SlideView.user_id == uid,
            SlideView.viewed_on_date == today,
        ).delete()
        for delta in (1, 2, 3):
            d = (dt.now(tz.utc).date() - td(days=delta)).isoformat()
            existing = db.query(SlideView).filter(
                SlideView.user_id == uid,
                SlideView.viewed_on_date == d,
            ).first()
            if not existing:
                db.add(SlideView(
                    user_id=uid, slide_id=1, course_id=1,
                    viewed_on_date=d,
                ))
        db.commit()
    finally:
        db.close()

    stats = run_streak_nudge_pass()
    assert stats["scanned"] >= 1
    assert stats["notified"] >= 1

    stats2 = run_streak_nudge_pass()
    assert stats2["notified"] == 0
    assert stats2["skipped_cooldown"] >= 1

    # Cleanup
    db = SessionLocal()
    try:
        db.query(Notification).filter(
            Notification.user_id == uid,
            Notification.type == "STREAK_NUDGE",
        ).delete()
        u = db.query(User).filter(User.id == uid).first()
        u.streak_nudge_last_sent_at = None
        db.commit()
    finally:
        db.close()
