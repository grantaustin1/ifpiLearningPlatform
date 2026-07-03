"""Iter 22 — Live Sessions router.

Endpoints:
- Admin:
    POST   /api/live-sessions               create
    PATCH  /api/live-sessions/{id}           update
    DELETE /api/live-sessions/{id}           cancel
    GET    /api/live-sessions                list (all in org)
    GET    /api/live-sessions/{id}           detail (with RSVPs + attendance)
    POST   /api/live-sessions/{id}/mark-attendance   bulk mark {user_ids: [], status: ATTENDED/NO_SHOW}

- Learner:
    GET    /api/live-sessions/upcoming       upcoming sessions for the current user (cohort-filtered)
    POST   /api/live-sessions/{id}/rsvp      toggle RSVP
    GET    /api/live-sessions/{id}/ics       download .ics calendar file (public + auth)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import LiveSession, LiveSessionRsvp, Organization, User

router = APIRouter(prefix="/api/live-sessions", tags=["Live Sessions"])


# ── Schemas ──────────────────────────────────────────────────────────
class LiveSessionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    meeting_url: HttpUrl
    start_at: datetime
    duration_minutes: int = Field(ge=5, le=8 * 60, default=60)
    host_name: Optional[str] = Field(default=None, max_length=200)
    cohort: Optional[str] = Field(default=None, max_length=100)
    course_id: Optional[int] = None
    max_attendees: Optional[int] = Field(default=None, ge=1)
    # Iter 23 — optional recurrence. Accepts an iCal RRULE without the
    # leading "RRULE:" prefix, e.g. "FREQ=WEEKLY;COUNT=8" or
    # "FREQ=DAILY;INTERVAL=2;UNTIL=20260901T000000Z". Materialised into
    # up to 26 child instances at creation time.
    recurrence_rule: Optional[str] = Field(default=None, max_length=500)


class LiveSessionPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    meeting_url: Optional[HttpUrl] = None
    start_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=8 * 60)
    host_name: Optional[str] = Field(default=None, max_length=200)
    cohort: Optional[str] = Field(default=None, max_length=100)
    max_attendees: Optional[int] = Field(default=None, ge=1)


class MarkAttendanceIn(BaseModel):
    user_ids: List[int] = Field(min_length=1)
    status: str = Field(pattern="^(ATTENDED|NO_SHOW)$")


# ── Helpers ──────────────────────────────────────────────────────────
def _serialize(s: LiveSession, include_rsvps: bool = False) -> dict:
    out = {
        "id": s.id,
        "title": s.title,
        "description": s.description,
        "meeting_url": s.meeting_url,
        "start_at": s.start_at.isoformat() if s.start_at else None,
        "duration_minutes": s.duration_minutes,
        "host_name": s.host_name,
        "cohort": s.cohort,
        "course_id": s.course_id,
        "max_attendees": s.max_attendees,
        "recurrence_rule": s.recurrence_rule,
        "parent_series_id": s.parent_series_id,
        "reminder_sent_at": s.reminder_sent_at.isoformat() if s.reminder_sent_at else None,
        "cancelled_at": s.cancelled_at.isoformat() if s.cancelled_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "rsvp_count": len([r for r in s.rsvps if r.status != "CANCELLED"]),
        "attendance_count": len([r for r in s.rsvps if r.status == "ATTENDED"]),
    }
    if include_rsvps:
        out["rsvps"] = [{
            "user_id": r.user_id,
            "status": r.status,
            "rsvped_at": r.rsvped_at.isoformat() if r.rsvped_at else None,
            "attendance_marked_at": r.attendance_marked_at.isoformat() if r.attendance_marked_at else None,
        } for r in s.rsvps]
    return out


# ── Recurrence helper ────────────────────────────────────────────────
# Cap at 26 instances (~6 months weekly) to keep the DB row count in
# check while still covering realistic term-length cohorts.
_MAX_RECURRENCE_INSTANCES = 26


def _expand_recurrence(rrule_str: str, dtstart: datetime) -> list[datetime]:
    """Return a list of concrete `datetime`s for the recurrence,
    excluding the seed dtstart (which is the head). Empty on parse error
    to keep failures graceful — the head instance is still created.

    Note: python-dateutil's `rrulestr` truncates microseconds on emitted
    occurrences, so we compare on second-resolution to detect the
    dtstart's "twin" and skip it — otherwise the head would be
    duplicated as a child."""
    from dateutil.rrule import rrulestr

    try:
        rule = rrulestr(rrule_str, dtstart=dtstart)
    except Exception:
        return []
    seed_seconds = dtstart.replace(microsecond=0)
    out: list[datetime] = []
    for occurrence in rule:
        # Skip the head's twin (first occurrence when the RRULE includes dtstart)
        if occurrence.replace(microsecond=0) == seed_seconds and not out:
            continue
        out.append(occurrence)
        if len(out) >= _MAX_RECURRENCE_INSTANCES:
            break
    return out


# ── Admin routes ─────────────────────────────────────────────────────
@router.post("", status_code=201)
def create_session(body: LiveSessionIn, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    # Normalise timezone: coerce naive → UTC
    start = body.start_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    head = LiveSession(
        organization_id=current.organization_id,
        title=body.title,
        description=body.description,
        meeting_url=str(body.meeting_url),
        start_at=start,
        duration_minutes=body.duration_minutes,
        host_name=body.host_name,
        cohort=body.cohort,
        course_id=body.course_id,
        max_attendees=body.max_attendees,
        recurrence_rule=body.recurrence_rule,
        created_by_id=current.id,
    )
    db.add(head); db.flush()  # need head.id for children's parent_series_id
    instances_created = 0
    if body.recurrence_rule:
        for occurrence_dt in _expand_recurrence(body.recurrence_rule, start):
            child = LiveSession(
                organization_id=current.organization_id,
                title=body.title,
                description=body.description,
                meeting_url=str(body.meeting_url),
                start_at=occurrence_dt,
                duration_minutes=body.duration_minutes,
                host_name=body.host_name,
                cohort=body.cohort,
                course_id=body.course_id,
                max_attendees=body.max_attendees,
                parent_series_id=head.id,  # child instance — no RRULE of its own
                created_by_id=current.id,
            )
            db.add(child)
            instances_created += 1
    db.commit(); db.refresh(head)
    result = _serialize(head)
    result["series_instances_created"] = instances_created
    return result


@router.get("")
def list_sessions(
    upcoming: bool = False,
    cohort: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    q = db.query(LiveSession).filter(LiveSession.organization_id == current.organization_id)
    if upcoming:
        q = q.filter(LiveSession.start_at >= datetime.now(timezone.utc) - timedelta(minutes=30))
    if cohort:
        q = q.filter(LiveSession.cohort == cohort)
    rows = q.order_by(LiveSession.start_at.asc()).all()
    return {"sessions": [_serialize(s) for s in rows]}


@router.get("/upcoming")
def list_upcoming_for_learner(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """List sessions the current user can RSVP to: their cohort (or
    sessions with no cohort restriction)."""
    user = db.query(User).filter(User.id == current.id).first()
    now = datetime.now(timezone.utc)
    q = db.query(LiveSession).filter(
        LiveSession.organization_id == current.organization_id,
        LiveSession.start_at >= now - timedelta(minutes=30),
        LiveSession.cancelled_at.is_(None),  # Iter 24 — hide cancelled from learners
    )
    rows = q.order_by(LiveSession.start_at.asc()).all()
    # Filter cohort in Python (small N)
    visible = [
        s for s in rows
        if (not s.cohort) or (user and s.cohort == user.cohort)
    ]
    # Enrich with the current user's RSVP status for each
    my_rsvps = {r.session_id: r for r in db.query(LiveSessionRsvp).filter(
        LiveSessionRsvp.user_id == current.id,
        LiveSessionRsvp.session_id.in_([s.id for s in visible] or [0]),
    ).all()}
    out = []
    for s in visible:
        row = _serialize(s)
        r = my_rsvps.get(s.id)
        row["my_rsvp_status"] = r.status if r else None
        out.append(row)
    return {"sessions": out}


@router.get("/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return _serialize(s, include_rsvps=True)


@router.patch("/{session_id}")
def update_session(session_id: int, body: LiveSessionPatch,
                   db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    patch = body.model_dump(exclude_unset=True)
    if "meeting_url" in patch:
        patch["meeting_url"] = str(patch["meeting_url"])
    if "start_at" in patch and patch["start_at"] and patch["start_at"].tzinfo is None:
        patch["start_at"] = patch["start_at"].replace(tzinfo=timezone.utc)
    for k, v in patch.items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return _serialize(s)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, cascade_series: bool = False,
                   db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if cascade_series and (s.recurrence_rule or s.parent_series_id):
        # Head to cascade from: either this row (if it's the head) or its parent.
        head_id = s.id if s.recurrence_rule else s.parent_series_id
        # Delete all children first (they FK to the head), then the head
        db.query(LiveSession).filter(LiveSession.parent_series_id == head_id).delete(
            synchronize_session=False)
        db.query(LiveSession).filter(LiveSession.id == head_id).delete(
            synchronize_session=False)
    else:
        db.delete(s)
    db.commit()


@router.post("/{session_id}/cancel")
def cancel_occurrence(session_id: int, db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Iter 24 — Cancel a single occurrence (RRULE EXDATE semantics).
    The row is soft-cancelled (stamped `cancelled_at`) rather than hard-
    deleted so RSVP + attendance history is preserved for audit, and the
    parent series' `.ics` export can emit a proper EXDATE line."""
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s.cancelled_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(s)
    return _serialize(s)


@router.post("/{session_id}/uncancel")
def uncancel_occurrence(session_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s.cancelled_at = None
    db.commit(); db.refresh(s)
    return _serialize(s)


# ── RSVP ─────────────────────────────────────────────────────────────
@router.post("/{session_id}/rsvp")
def toggle_rsvp(session_id: int, series: bool = False,
                db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    """RSVP to a single session (default) OR the whole series when
    `?series=true` is passed against a series-head id (Iter 24 Cohort
    Enrollment). Learners toggle once and receive all future
    occurrences on their calendar automatically."""
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # ── Series-wide RSVP (Iter 24) ──────────────────────────────────
    if series:
        head_id = s.id if s.recurrence_rule else s.parent_series_id
        if head_id is None:
            raise HTTPException(
                status_code=400,
                detail="Session is not part of a recurring series",
            )
        # Collect head + all children that are still upcoming and not cancelled
        now = datetime.now(timezone.utc)
        series_rows = (
            db.query(LiveSession).filter(
                or_(LiveSession.id == head_id,
                    LiveSession.parent_series_id == head_id),
                LiveSession.start_at >= now - timedelta(minutes=30),
                LiveSession.cancelled_at.is_(None),
            ).all()
        )
        # Check if learner is currently RSVP'd on any of them
        existing = {
            r.session_id: r for r in db.query(LiveSessionRsvp).filter(
                LiveSessionRsvp.session_id.in_([x.id for x in series_rows]),
                LiveSessionRsvp.user_id == current.id,
            ).all()
        }
        any_active = any(r.status == "RSVP" for r in existing.values())
        target_status = "CANCELLED" if any_active else "RSVP"
        touched = 0
        for row in series_rows:
            r = existing.get(row.id)
            if r:
                r.status = target_status
            else:
                if target_status == "RSVP":
                    db.add(LiveSessionRsvp(
                        session_id=row.id, user_id=current.id, status="RSVP",
                    ))
            touched += 1
        db.commit()
        return {"status": target_status, "series_count": touched}

    # ── Single-occurrence RSVP (original path) ──────────────────────
    rsvp = db.query(LiveSessionRsvp).filter(
        LiveSessionRsvp.session_id == session_id,
        LiveSessionRsvp.user_id == current.id,
    ).first()
    if rsvp:
        # Toggle: RSVP → CANCELLED → RSVP
        rsvp.status = "CANCELLED" if rsvp.status == "RSVP" else "RSVP"
        db.commit(); db.refresh(rsvp)
        return {"status": rsvp.status}
    # Enforce max_attendees
    if s.max_attendees:
        current_rsvps = db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.session_id == session_id,
            LiveSessionRsvp.status != "CANCELLED",
        ).count()
        if current_rsvps >= s.max_attendees:
            raise HTTPException(status_code=400, detail="Session is full")
    rsvp = LiveSessionRsvp(session_id=session_id, user_id=current.id, status="RSVP")
    db.add(rsvp); db.commit(); db.refresh(rsvp)
    return {"status": rsvp.status}


# ── Attendance ───────────────────────────────────────────────────────
@router.post("/{session_id}/mark-attendance")
def mark_attendance(session_id: int, body: MarkAttendanceIn,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    marked = 0
    for uid in body.user_ids:
        rsvp = db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.session_id == session_id,
            LiveSessionRsvp.user_id == uid,
        ).first()
        if not rsvp:
            # Auto-create an RSVP row so walk-ins get tracked
            rsvp = LiveSessionRsvp(session_id=session_id, user_id=uid, status="RSVP")
            db.add(rsvp); db.flush()
        rsvp.status = body.status
        rsvp.attendance_marked_at = datetime.now(timezone.utc)
        marked += 1
    db.commit()
    return {"marked": marked, "status": body.status}


# ── ICS export ───────────────────────────────────────────────────────
def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


@router.get("/{session_id}/ics")
def download_ics(session_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(get_current_user)):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    start = s.start_at.astimezone(timezone.utc) if s.start_at.tzinfo else s.start_at.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=s.duration_minutes)
    desc_line = (s.description or "") + "\n\nJoin: " + s.meeting_url
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IFPI Learning//Live Sessions//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:live-session-{s.id}@ifpi.org",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_ics_escape(s.title)}",
        f"DESCRIPTION:{_ics_escape(desc_line)}",
        f"URL:{s.meeting_url}",
        f"LOCATION:{_ics_escape(s.meeting_url)}",
    ]
    # Iter 24 — If this is a series head, emit RRULE + EXDATEs for
    # cancelled children so subscribed calendar clients accurately
    # reflect skipped occurrences.
    if s.recurrence_rule:
        lines.append(f"RRULE:{s.recurrence_rule}")
        cancelled_children = db.query(LiveSession).filter(
            LiveSession.parent_series_id == s.id,
            LiveSession.cancelled_at.isnot(None),
        ).all()
        for child in cancelled_children:
            ex = child.start_at.astimezone(timezone.utc) if child.start_at.tzinfo else child.start_at.replace(tzinfo=timezone.utc)
            lines.append(f"EXDATE:{ex.strftime('%Y%m%dT%H%M%SZ')}")
    if s.cancelled_at:
        lines.append("STATUS:CANCELLED")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    ics = "\r\n".join(lines)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="live-session-{s.id}.ics"'},
    )


# ── ICS subscription URL (Iter 24) ───────────────────────────────────
# Persistent, calendar-app-friendly URL that returns ALL upcoming
# sessions for a user (instructor or learner). Token is a compact
# HMAC-signed payload with `sub` (user_id) and `kind` (`admin`|`learner`).
# No DB row — rotation is via secret change or expiry, both acceptable
# for calendar subscription semantics.

import base64
import hashlib
import hmac
import json
import os


def _sub_secret() -> bytes:
    """Signing key for subscription tokens. Uses JWT_SECRET so
    ops don't need to configure yet another secret."""
    return (os.environ.get("JWT_SECRET") or "dev-only-secret").encode()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign_subscription_token(user_id: int, kind: str, org_id: int, version: int) -> str:
    """Payload includes `sv` (secret version scoped to the org). Bumping
    the org's `subscription_secret_version` column invalidates every
    token issued at the old version — the calendar URL 404s but the
    user's login session is untouched."""
    payload = json.dumps({
        "sub": user_id, "kind": kind, "org": org_id, "sv": version,
    }, sort_keys=True).encode()
    sig = hmac.new(_sub_secret(), payload, hashlib.sha256).digest()
    return f"{_b64url(payload)}.{_b64url(sig)}"


def _verify_subscription_token(token: str) -> dict | None:
    try:
        payload_b64, sig_b64 = token.split(".")
        payload = _b64url_decode(payload_b64)
        expected_sig = hmac.new(_sub_secret(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
            return None
        return json.loads(payload)
    except Exception:
        return None


@router.post("/subscribe-url")
def create_subscription_url(kind: str = "admin", db: Session = Depends(get_db),
                            current: CurrentUser = Depends(get_current_user)):
    """Return a URL the caller can hand to their calendar app. The URL
    is idempotent for a given (user_id, kind, org, secret-version) —
    rotating the org's subscription_secret_version issues a fresh URL
    and kills all outstanding ones."""
    if kind not in ("admin", "learner"):
        raise HTTPException(status_code=400, detail="kind must be 'admin' or 'learner'")
    if kind == "admin":
        if not current.has_any_role({"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"}):
            raise HTTPException(status_code=403, detail="Not authorised for admin subscription")
    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    version = org.subscription_secret_version if org else 1
    token = _sign_subscription_token(current.id, kind, current.organization_id, version)
    return {"token": token, "path": f"/api/live-sessions/subscribe/{token}.ics",
            "secret_version": version}


@router.post("/subscribe-url/rotate")
def rotate_subscription_secret(db: Session = Depends(get_db),
                                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Iter 25 — Bump the org's subscription_secret_version. Every
    outstanding subscription URL for this org immediately 401s; each
    user must fetch a fresh URL from /subscribe-url. Does NOT log out
    users (unlike rotating JWT_SECRET)."""
    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    old = org.subscription_secret_version or 1
    org.subscription_secret_version = old + 1
    db.commit()
    return {"old_version": old, "new_version": org.subscription_secret_version,
            "rotated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/subscribe/{token}.ics")
def subscribe_ics(token: str, db: Session = Depends(get_db)):
    """Iter 24 — Persistent calendar subscription. Token authenticates
    the request; NO cookie/JWT required (calendar apps don't send them).
    Returns a text/calendar bundle of the user's upcoming sessions.

    Iter 25 — Also verifies the org's `subscription_secret_version`
    matches the payload's `sv`. If admin has rotated the secret since
    the token was issued, the URL 401s."""
    payload = _verify_subscription_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid subscription token")

    user_id = payload["sub"]
    kind = payload["kind"]
    token_sv = payload.get("sv", 1)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    current_sv = org.subscription_secret_version if org else 1
    if current_sv != token_sv:
        raise HTTPException(status_code=401, detail="Subscription URL revoked (secret rotated)")

    now = datetime.now(timezone.utc)
    q = db.query(LiveSession).filter(
        LiveSession.organization_id == user.organization_id,
        LiveSession.start_at >= now - timedelta(days=1),
        LiveSession.cancelled_at.is_(None),
    )
    if kind == "learner":
        # Only sessions matching the learner's cohort (or unrestricted)
        # AND that they've RSVP'd to (or open sessions with no RSVP required).
        all_upcoming = q.order_by(LiveSession.start_at.asc()).all()
        # Filter to cohort match
        cohort_ok = [s for s in all_upcoming if (not s.cohort) or s.cohort == user.cohort]
        # Include sessions the learner has RSVP'd to (any cohort)
        my_rsvps = {r.session_id for r in db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.user_id == user_id,
            LiveSessionRsvp.status == "RSVP",
        ).all()}
        sessions = [s for s in cohort_ok if not s.cohort or s.id in my_rsvps or True]
        # (For simplicity we include all cohort-visible upcoming, matching
        # the /upcoming endpoint semantics. Learner can un-RSVP later.)
    else:
        # Admin kind = all upcoming sessions in the org
        sessions = q.order_by(LiveSession.start_at.asc()).all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IFPI Learning//Live Sessions Subscription//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:IFPI Live Sessions ({kind})",
        f"X-WR-CALDESC:Auto-updating subscription for {user.email}",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for s in sessions:
        start = s.start_at.astimezone(timezone.utc) if s.start_at.tzinfo else s.start_at.replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=s.duration_minutes)
        desc = (s.description or "") + "\n\nJoin: " + s.meeting_url
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:live-session-{s.id}@ifpi.org",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{_ics_escape(s.title)}",
            f"DESCRIPTION:{_ics_escape(desc)}",
            f"URL:{s.meeting_url}",
            f"LOCATION:{_ics_escape(s.meeting_url)}",
            "END:VEVENT",
        ])
    lines.extend(["END:VCALENDAR", ""])
    body = "\r\n".join(lines)
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Cache-Control": "public, max-age=900"},  # 15 min cache — calendar apps re-poll often
    )



@router.get("/subscribe-url/qr")
def subscribe_url_qr(
    kind: str = "admin",
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 25 — Return an SVG QR code encoding the current user's
    subscription URL. Instructors screen-share this on a slide so
    learners can scan directly from their phones. Cheap to generate
    (~5ms), no caching needed — regenerated on each request so a
    secret rotation produces a fresh code immediately."""
    if kind not in ("admin", "learner"):
        raise HTTPException(status_code=400, detail="kind must be 'admin' or 'learner'")
    if kind == "admin" and not current.has_any_role({"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"}):
        raise HTTPException(status_code=403, detail="Not authorised for admin subscription")

    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    version = org.subscription_secret_version if org else 1
    token = _sign_subscription_token(current.id, kind, current.organization_id, version)

    # Build the absolute URL from the incoming request-independent
    # `PUBLIC_BASE_URL` env var if set (Cloudflare-friendly), else fall
    # back to the well-known path.
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    url = f"{base}/api/live-sessions/subscribe/{token}.ics" if base else \
          f"/api/live-sessions/subscribe/{token}.ics"

    import qrcode
    import qrcode.image.svg as svg
    qr = qrcode.QRCode(box_size=8, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(image_factory=svg.SvgPathImage)
    import io as _io
    buf = _io.BytesIO()
    img.save(buf)
    svg_bytes = buf.getvalue()
    return Response(
        content=svg_bytes, media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )

