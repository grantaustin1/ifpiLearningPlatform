"""Iter 24 — EXDATE cancellation + Instructor ICS subscription URL tests.

Covers:
- POST /live-sessions/{id}/cancel stamps `cancelled_at`, keeps the row
  (soft-delete) and hides it from learner /upcoming feed.
- Cancelling one occurrence in a series does NOT touch the head or
  sibling children.
- POST /live-sessions/{id}/uncancel restores it.
- Head's `.ics` export emits RRULE + EXDATE for each cancelled child.
- Reminder worker skips cancelled sessions.
- POST /live-sessions/subscribe-url returns a signed token URL.
- GET /live-sessions/subscribe/{token}.ics returns text/calendar with
  every upcoming session, WITHOUT requiring cookie/JWT auth.
- Bad token rejected with 401.
- kind=admin gated behind admin/instructor role.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

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


@pytest.fixture()
def series(admin):
    """Create a 4-occurrence weekly series (head + 3 children)."""
    start = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter24-exdate-series",
        "meeting_url": "https://zoom.us/j/24a",
        "start_at": start,
        "duration_minutes": 30,
        "recurrence_rule": "FREQ=WEEKLY;COUNT=4",
    }, timeout=15)
    assert r.status_code == 201
    head_id = r.json()["id"]
    # Grab all series rows in start-order to find children
    rows = admin.get(f"{BASE_URL}/api/live-sessions", timeout=10).json()["sessions"]
    child_ids = [
        s["id"] for s in rows
        if s.get("parent_series_id") == head_id
    ]
    yield {"head_id": head_id, "child_ids": child_ids}
    admin.delete(f"{BASE_URL}/api/live-sessions/{head_id}?cascade_series=true", timeout=10)


# ── EXDATE cancel ────────────────────────────────────────────────────
def test_cancel_occurrence_soft_deletes_and_hides_from_learner(admin, learner, series):
    child = series["child_ids"][0]
    r = admin.post(f"{BASE_URL}/api/live-sessions/{child}/cancel", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["cancelled_at"] is not None

    # Admin can still see it via GET
    g = admin.get(f"{BASE_URL}/api/live-sessions/{child}", timeout=10).json()
    assert g["cancelled_at"] is not None

    # Learner /upcoming must NOT include it
    up = learner.get(f"{BASE_URL}/api/live-sessions/upcoming", timeout=10).json()
    ids = [s["id"] for s in up["sessions"]]
    assert child not in ids, f"cancelled session leaked into learner /upcoming: {ids}"

    # Siblings still visible
    other_children = [c for c in series["child_ids"] if c != child]
    # (Not asserting they're in /upcoming because cohort filter etc. —
    # just verify they're not cancelled)
    for oc in other_children:
        g = admin.get(f"{BASE_URL}/api/live-sessions/{oc}", timeout=10).json()
        assert g["cancelled_at"] is None


def test_uncancel_restores_occurrence(admin, series):
    child = series["child_ids"][1]
    admin.post(f"{BASE_URL}/api/live-sessions/{child}/cancel", timeout=10)
    r = admin.post(f"{BASE_URL}/api/live-sessions/{child}/uncancel", timeout=10)
    assert r.status_code == 200
    assert r.json()["cancelled_at"] is None


def test_head_ics_exports_rrule_and_exdate(admin, series):
    head = series["head_id"]
    child = series["child_ids"][0]
    admin.post(f"{BASE_URL}/api/live-sessions/{child}/cancel", timeout=10)
    r = admin.get(f"{BASE_URL}/api/live-sessions/{head}/ics", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert "RRULE:FREQ=WEEKLY;COUNT=4" in body, "head .ics must include the RRULE"
    assert "EXDATE:" in body, "head .ics must include an EXDATE for the cancelled child"


def test_reminder_worker_skips_cancelled_session(admin, learner):
    """Direct-DB test: a cancelled session in the 15-min window is NOT
    reminded, even if RSVPs exist."""
    from core.database import SessionLocal
    from models import LiveSession, LiveSessionRsvp, OutboxMessage
    from services.live_session_reminder_worker import tick

    with SessionLocal() as db:
        me = learner.get(f"{BASE_URL}/api/auth/me", timeout=10).json()
        now = datetime.now(timezone.utc)
        s = LiveSession(
            organization_id=1,
            title="iter24-cancelled-should-not-remind",
            meeting_url="https://zoom.us/j/24z",
            start_at=now + timedelta(minutes=15),
            duration_minutes=30,
            created_by_id=1,
            cancelled_at=now,  # already cancelled
        )
        db.add(s); db.flush()
        db.add(LiveSessionRsvp(session_id=s.id, user_id=me["id"], status="RSVP"))
        db.commit()
        sid = s.id
        try:
            before = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()
            tick(db)
            after = db.query(OutboxMessage).filter(
                OutboxMessage.template == "live_session_reminder"
            ).count()
            assert after == before, "cancelled session must NOT trigger reminders"
        finally:
            db.query(LiveSessionRsvp).filter(LiveSessionRsvp.session_id == sid).delete(
                synchronize_session=False)
            db.query(LiveSession).filter(LiveSession.id == sid).delete(
                synchronize_session=False)
            db.commit()


# ── Subscription URL ─────────────────────────────────────────────────
def test_admin_can_generate_admin_subscription_url(admin):
    r = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "token" in d and "path" in d
    assert d["path"].startswith("/api/live-sessions/subscribe/")
    assert d["path"].endswith(".ics")


def test_learner_cannot_generate_admin_subscription(learner):
    r = learner.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10)
    assert r.status_code == 403


def test_learner_can_generate_learner_subscription(learner):
    r = learner.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=learner", timeout=10)
    assert r.status_code == 200
    assert "token" in r.json()


def test_subscription_endpoint_returns_ics_without_auth(admin, series):
    """Cornerstone: the subscription URL must work with NO auth headers
    (calendar apps don't send cookies/JWT)."""
    d = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10).json()
    token = d["token"]
    # Fresh anonymous requests.Session — proves no cookie leakage
    anon = requests.Session()
    r = anon.get(f"{BASE_URL}/api/live-sessions/subscribe/{token}.ics", timeout=10)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in body
    # Should list our test series
    assert "iter24-exdate-series" in body


def test_subscription_bad_token_rejected():
    r = requests.get(f"{BASE_URL}/api/live-sessions/subscribe/nonsense.ics", timeout=10)
    assert r.status_code == 401


def test_subscription_tampered_token_rejected(admin):
    d = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10).json()
    token = d["token"]
    # Flip a character in the middle of the signature (the final char's
    # low bits are base64 padding spare bits — flipping them is a no-op)
    payload_b64, sig_b64 = token.split(".")
    mid = len(sig_b64) // 2
    flipped = "A" if sig_b64[mid] != "A" else "B"
    tampered = f"{payload_b64}.{sig_b64[:mid]}{flipped}{sig_b64[mid + 1:]}"
    r = requests.get(f"{BASE_URL}/api/live-sessions/subscribe/{tampered}.ics", timeout=10)
    assert r.status_code == 401


def test_subscription_url_idempotent_for_same_user(admin):
    """Same user + kind → same token (as long as JWT_SECRET is stable)."""
    r1 = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10).json()
    r2 = admin.post(f"{BASE_URL}/api/live-sessions/subscribe-url?kind=admin", timeout=10).json()
    assert r1["token"] == r2["token"]


# ── Cohort Enrollment (Iter 24 improvement) ──────────────────────────
def test_series_rsvp_creates_rsvp_on_head_and_all_children(admin, learner):
    """One-click series RSVP on the head → active RSVP for the head +
    every remaining upcoming child."""
    start = (datetime.now(timezone.utc) + timedelta(days=21)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter24-cohort-enrol-series",
        "meeting_url": "https://zoom.us/j/24c",
        "start_at": start,
        "duration_minutes": 30,
        "recurrence_rule": "FREQ=WEEKLY;COUNT=3",  # head + 2 children
    }, timeout=15)
    assert r.status_code == 201
    head_id = r.json()["id"]

    try:
        rsvp = learner.post(f"{BASE_URL}/api/live-sessions/{head_id}/rsvp?series=true", timeout=10)
        assert rsvp.status_code == 200
        d = rsvp.json()
        assert d["status"] == "RSVP"
        assert d["series_count"] == 3, f"expected 3 sessions RSVP'd, got {d}"

        # Learner's /upcoming should now include all 3 with my_rsvp_status='RSVP'
        up = learner.get(f"{BASE_URL}/api/live-sessions/upcoming", timeout=10).json()
        series_up = [s for s in up["sessions"]
                     if s.get("parent_series_id") == head_id or s["id"] == head_id]
        assert len(series_up) == 3
        assert all(s["my_rsvp_status"] == "RSVP" for s in series_up), \
            [s["my_rsvp_status"] for s in series_up]

        # Toggle again — cancels all 3
        rsvp2 = learner.post(f"{BASE_URL}/api/live-sessions/{head_id}/rsvp?series=true", timeout=10).json()
        assert rsvp2["status"] == "CANCELLED"
        # No sessions in learner /upcoming with active RSVP anymore
        up2 = learner.get(f"{BASE_URL}/api/live-sessions/upcoming", timeout=10).json()
        series_up2 = [s for s in up2["sessions"]
                      if s.get("parent_series_id") == head_id or s["id"] == head_id]
        assert all(s["my_rsvp_status"] in ("CANCELLED", None) for s in series_up2)
    finally:
        admin.delete(f"{BASE_URL}/api/live-sessions/{head_id}?cascade_series=true", timeout=10)


def test_series_rsvp_on_non_series_session_400(admin, learner):
    """Passing ?series=true against a stand-alone session is a 400."""
    start = (datetime.now(timezone.utc) + timedelta(days=22)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter24-cohort-standalone",
        "meeting_url": "https://zoom.us/j/24d",
        "start_at": start,
    }, timeout=10)
    sid = r.json()["id"]
    try:
        r2 = learner.post(f"{BASE_URL}/api/live-sessions/{sid}/rsvp?series=true", timeout=10)
        assert r2.status_code == 400
        # Global exception handler wraps FastAPI HTTPException detail into
        # `{"error": {"code": ..., "message": ...}}`; older layers just use `detail`.
        body = r2.json()
        message = (body.get("detail")
                   or body.get("error", {}).get("message")
                   or "").lower()
        assert "series" in message, body
    finally:
        admin.delete(f"{BASE_URL}/api/live-sessions/{sid}", timeout=10)


def test_series_rsvp_skips_cancelled_children(admin, learner):
    """Cancelled children (EXDATE) must NOT get an RSVP created."""
    start = (datetime.now(timezone.utc) + timedelta(days=23)).isoformat()
    r = admin.post(f"{BASE_URL}/api/live-sessions", json={
        "title": "iter24-cohort-cancel-skip",
        "meeting_url": "https://zoom.us/j/24e",
        "start_at": start,
        "recurrence_rule": "FREQ=WEEKLY;COUNT=3",
    }, timeout=10)
    head_id = r.json()["id"]
    # Cancel middle child
    rows = admin.get(f"{BASE_URL}/api/live-sessions", timeout=10).json()["sessions"]
    children = sorted(
        [s for s in rows if s.get("parent_series_id") == head_id],
        key=lambda s: s["start_at"],
    )
    admin.post(f"{BASE_URL}/api/live-sessions/{children[0]['id']}/cancel", timeout=10)

    try:
        rsvp = learner.post(f"{BASE_URL}/api/live-sessions/{head_id}/rsvp?series=true", timeout=10).json()
        # Only 2 non-cancelled remaining (head + last child)
        assert rsvp["series_count"] == 2, f"cancelled child should be skipped, got {rsvp}"
    finally:
        admin.delete(f"{BASE_URL}/api/live-sessions/{head_id}?cascade_series=true", timeout=10)
