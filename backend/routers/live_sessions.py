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
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import LiveSession, LiveSessionRsvp, User

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


# ── Admin routes ─────────────────────────────────────────────────────
@router.post("", status_code=201)
def create_session(body: LiveSessionIn, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    # Normalise timezone: coerce naive → UTC
    start = body.start_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    s = LiveSession(
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
        created_by_id=current.id,
    )
    db.add(s); db.commit(); db.refresh(s)
    return _serialize(s)


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
def delete_session(session_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(s); db.commit()


# ── RSVP ─────────────────────────────────────────────────────────────
@router.post("/{session_id}/rsvp")
def toggle_rsvp(session_id: int, db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
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
    ics = "\r\n".join([
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
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="live-session-{s.id}.ics"'},
    )
