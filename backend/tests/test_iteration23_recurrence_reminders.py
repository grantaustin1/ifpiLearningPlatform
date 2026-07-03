"""Iter 23 — Live Session recurrence + 15-min reminder worker tests.

Covers:
- Recurrence: creating a session with RRULE materialises N child instances
  (each with parent_series_id set to the head's id).
- Cascade delete: `?cascade_series=true` on the head removes all children.
- Recurrence cap: extreme RRULEs like `FREQ=DAILY;COUNT=1000` are capped
  at 26 instances (protects the DB).
- Reminder worker: sessions in the 14–16 min pre-start window with
  reminder_sent_at IS NULL queue emails to every active RSVP and stamp
  reminder_sent_at. Sessions outside the window are untouched.
- Idempotency: running the worker twice does not double-send.
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


# ── Recurrence ───────────────────────────────────────────────────────
def test_create_weekly_recurrence_materialises_children(admin):
    start = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter23-weekly",
        "meeting_url": "https://zoom.us/j/23a",
        "start_at": start,
        "duration_minutes": 60,
        "recurrence_rule": "FREQ=WEEKLY;COUNT=5",
    }, timeout=15)
    assert r.status_code == 201, r.text
    d = r.json()
    head_id = d["id"]
    assert d["recurrence_rule"] == "FREQ=WEEKLY;COUNT=5"
    assert d["series_instances_created"] == 4  # 5 total incl. head; 4 children
    try:
        # Cascade delete cleans up the whole series
        rows_before = admin.get(f"{BASE_URL}/api/live-sessions", timeout=10).json()["sessions"]
        series_ids = [
            s["id"] for s in rows_before
            if s.get("parent_series_id") == head_id or s["id"] == head_id
        ]
        assert len(series_ids) == 5, f"expected 5 sessions in series, found {len(series_ids)}"
    finally:
        admin.delete(f"{BASE_URL}/api/live-sessions/{head_id}?cascade_series=true", timeout=10)
    # Post-cascade: all series rows are gone
    rows_after = admin.get(f"{BASE_URL}/api/live-sessions", timeout=10).json()["sessions"]
    remaining = [s for s in rows_after if s.get("parent_series_id") == head_id or s["id"] == head_id]
    assert remaining == [], f"cascade_series=true should remove all series rows, got {remaining}"


def test_recurrence_capped_at_26_instances(admin):
    """Extreme RRULE with COUNT=1000 must be capped to protect the DB."""
    start = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter23-cap-test",
        "meeting_url": "https://zoom.us/j/23b",
        "start_at": start,
        "recurrence_rule": "FREQ=DAILY;COUNT=1000",
    }, timeout=10)
    assert r.status_code == 201
    head_id = r.json()["id"]
    # 26 max children (27 total incl. head)
    assert r.json()["series_instances_created"] == 26
    admin.delete(f"{BASE_URL}/api/live-sessions/{head_id}?cascade_series=true", timeout=10)


def test_invalid_rrule_falls_back_to_single_session(admin):
    """A garbage RRULE should not 500; the head is still created with
    zero children (graceful degradation)."""
    start = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter23-bad-rrule",
        "meeting_url": "https://zoom.us/j/23c",
        "start_at": start,
        "recurrence_rule": "GARBAGE=RULE",
    }, timeout=10)
    assert r.status_code == 201
    assert r.json()["series_instances_created"] == 0
    admin.delete(f"{BASE_URL}/api/live-sessions/{r.json()['id']}", timeout=10)


# ── Reminder worker ──────────────────────────────────────────────────
def test_reminder_worker_sends_emails_in_14_16_min_window(admin, learner):
    """Session starting in exactly 15 minutes should get its RSVPs
    reminded. Session starting in 60 minutes should NOT."""
    # Direct-DB access lets us set the exact start_at and observe worker output
    import sys
    sys.path.insert(0, "/app/backend")
    from core.database import SessionLocal
    from models import LiveSession, LiveSessionRsvp, OutboxMessage
    from services.live_session_reminder_worker import tick

    with SessionLocal() as db:
        # Grab a learner user id
        me = learner.get(f"{BASE_URL}/api/auth/me", timeout=10).json()

        now = datetime.now(timezone.utc)
        s_soon = LiveSession(
            organization_id=1, title="iter23-reminder-in-window",
            meeting_url="https://zoom.us/j/23d",
            start_at=now + timedelta(minutes=15),
            duration_minutes=30, created_by_id=1,
        )
        s_far = LiveSession(
            organization_id=1, title="iter23-reminder-out-of-window",
            meeting_url="https://zoom.us/j/23e",
            start_at=now + timedelta(minutes=60),
            duration_minutes=30, created_by_id=1,
        )
        db.add_all([s_soon, s_far]); db.flush()
        db.add(LiveSessionRsvp(session_id=s_soon.id, user_id=me["id"], status="RSVP"))
        db.add(LiveSessionRsvp(session_id=s_far.id, user_id=me["id"], status="RSVP"))
        db.commit()
        s_soon_id, s_far_id = s_soon.id, s_far.id

        try:
            baseline = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()

            n = tick(db)
            assert n == 1, f"expected 1 session processed, got {n}"

            # Reminder stamped on the in-window session, not the far one
            db.expire_all()
            in_window = db.get(LiveSession, s_soon_id)
            out_of_window = db.get(LiveSession, s_far_id)
            assert in_window.reminder_sent_at is not None
            assert out_of_window.reminder_sent_at is None

            # 1 new outbox row for the RSVP'd learner
            new_count = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()
            assert new_count == baseline + 1, \
                f"expected +1 reminder message, got baseline={baseline} new={new_count}"

            # Idempotent — second tick does not re-send
            n2 = tick(db)
            assert n2 == 0, f"second tick should be a no-op, got {n2}"
            final_count = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()
            assert final_count == baseline + 1

        finally:
            # Cleanup — remove the test sessions and their RSVPs/outbox rows
            db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder",
                OutboxMessage.body_html.like("%iter23-reminder-in-window%"),
            ).delete(synchronize_session=False)
            db.query(LiveSessionRsvp).filter(
                LiveSessionRsvp.session_id.in_([s_soon_id, s_far_id])
            ).delete(synchronize_session=False)
            db.query(LiveSession).filter(
                LiveSession.id.in_([s_soon_id, s_far_id])
            ).delete(synchronize_session=False)
            db.commit()


def test_reminder_worker_skips_cancelled_rsvps(admin, learner):
    """A learner who cancelled their RSVP should NOT get a reminder."""
    import sys
    sys.path.insert(0, "/app/backend")
    from core.database import SessionLocal
    from models import LiveSession, LiveSessionRsvp, OutboxMessage
    from services.live_session_reminder_worker import tick

    with SessionLocal() as db:
        me = learner.get(f"{BASE_URL}/api/auth/me", timeout=10).json()
        now = datetime.now(timezone.utc)
        s = LiveSession(
            organization_id=1, title="iter23-reminder-cancelled-rsvp",
            meeting_url="https://zoom.us/j/23f",
            start_at=now + timedelta(minutes=15),
            duration_minutes=30, created_by_id=1,
        )
        db.add(s); db.flush()
        db.add(LiveSessionRsvp(
            session_id=s.id, user_id=me["id"], status="CANCELLED",
        ))
        db.commit()
        sid = s.id

        try:
            baseline = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()
            tick(db)
            final = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()
            assert final == baseline, \
                "CANCELLED RSVPs must NOT receive reminders"
        finally:
            db.query(LiveSessionRsvp).filter(
                LiveSessionRsvp.session_id == sid
            ).delete(synchronize_session=False)
            db.query(LiveSession).filter(
                LiveSession.id == sid
            ).delete(synchronize_session=False)
            db.commit()
