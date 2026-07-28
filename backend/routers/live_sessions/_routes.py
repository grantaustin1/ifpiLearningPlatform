from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import Enrollment, LiveSession, LiveSessionRsvp, User

from . import router
from ._helpers import _expand_recurrence, _serialize
from ._schemas import LiveSessionIn, LiveSessionPatch

logger = logging.getLogger(__name__)


# ── Admin routes ─────────────────────────────────────────────────────
@router.post("", status_code=201)
def create_session(body: LiveSessionIn, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
    db.add(head)
    db.flush()  # need head.id for children's parent_series_id
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
                parent_series_id=head.id,
                created_by_id=current.id,
            )
            db.add(child)
            instances_created += 1
    db.commit()
    db.refresh(head)
    result = _serialize(head)
    result["series_instances_created"] = instances_created
    return result


@router.get("")
def list_sessions(
    upcoming: bool = False,
    cohort: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> dict:
    # Iter 38 — was 86 queries via `s.rsvps` lazy-load per session
    # (twice — for rsvp_count and attendance_count). `selectinload`
    # collapses to 2 queries total.
    q = (db.query(LiveSession)
         .options(selectinload(LiveSession.rsvps))
         .filter(LiveSession.organization_id == current.organization_id))
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
) -> dict:
    """List sessions the current user can RSVP to: their cohort (or
    sessions with no cohort restriction)."""
    user = db.query(User).filter(User.id == current.id).first()
    now = datetime.now(timezone.utc)
    # Iter 38 — eager-load rsvps for the _serialize call
    q = (db.query(LiveSession)
         .options(selectinload(LiveSession.rsvps))
         .filter(
             LiveSession.organization_id == current.organization_id,
             LiveSession.start_at >= now - timedelta(minutes=30),
             LiveSession.cancelled_at.is_(None),
         ))
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
                current: CurrentUser = Depends(get_current_user)) -> dict:
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
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
    db.commit()
    db.refresh(s)
    return _serialize(s)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, cascade_series: bool = False,
                   db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> None:
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if cascade_series and (s.recurrence_rule or s.parent_series_id):
        head_id = s.id if s.recurrence_rule else s.parent_series_id
        db.query(LiveSession).filter(LiveSession.parent_series_id == head_id).delete(
            synchronize_session=False)
        db.query(LiveSession).filter(LiveSession.id == head_id).delete(
            synchronize_session=False)
    else:
        db.delete(s)
    db.commit()


@router.post("/{session_id}/cancel")
def cancel_occurrence(session_id: int, db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
    """Iter 24 — Cancel a single occurrence (RRULE EXDATE semantics).
    The row is soft-cancelled (stamped `cancelled_at`) rather than hard-
    deleted so RSVP + attendance history is preserved for audit."""
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(s)
    return _serialize(s)


@router.post("/{session_id}/uncancel")
def uncancel_occurrence(session_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s.cancelled_at = None
    db.commit()
    db.refresh(s)
    return _serialize(s)


# ── RSVP ─────────────────────────────────────────────────────────────
@router.post("/{session_id}/rsvp")
def toggle_rsvp(session_id: int, series: bool = False,
                db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)) -> dict:
    """RSVP to a single session (default) OR the whole series when
    `?series=true` is passed against a series-head id (Iter 24 Cohort
    Enrollment)."""
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
        now = datetime.now(timezone.utc)
        series_rows = (
            db.query(LiveSession).filter(
                or_(LiveSession.id == head_id,
                    LiveSession.parent_series_id == head_id),
                LiveSession.start_at >= now - timedelta(minutes=30),
                LiveSession.cancelled_at.is_(None),
            ).all()
        )
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
        head_row = next((x for x in series_rows if x.id == head_id), s)
        auto_enrolled = False
        if target_status == "RSVP" and head_row.course_id:
            existing_enrol = db.query(Enrollment).filter(
                Enrollment.user_id == current.id,
                Enrollment.course_id == head_row.course_id,
            ).first()
            if not existing_enrol:
                db.add(Enrollment(
                    user_id=current.id,
                    course_id=head_row.course_id,
                    progress=0.0,
                ))
                db.commit()
                auto_enrolled = True
        return {
            "status": target_status, "series_count": touched,
            "auto_enrolled": auto_enrolled,
            "course_id": head_row.course_id if auto_enrolled else None,
        }

    # ── Single-occurrence RSVP (original path) ──────────────────────
    rsvp = db.query(LiveSessionRsvp).filter(
        LiveSessionRsvp.session_id == session_id,
        LiveSessionRsvp.user_id == current.id,
    ).first()
    if rsvp:
        rsvp.status = "CANCELLED" if rsvp.status == "RSVP" else "RSVP"
        db.commit()
        db.refresh(rsvp)
        return {"status": rsvp.status, "auto_enrolled": False,
                "course_id": None}
    # Enforce max_attendees
    if s.max_attendees:
        current_rsvps = db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.session_id == session_id,
            LiveSessionRsvp.status != "CANCELLED",
        ).count()
        if current_rsvps >= s.max_attendees:
            raise HTTPException(status_code=400, detail="Session is full")
    rsvp = LiveSessionRsvp(session_id=session_id, user_id=current.id, status="RSVP")
    db.add(rsvp)
    auto_enrolled = False
    if s.course_id:
        existing_enrol = db.query(Enrollment).filter(
            Enrollment.user_id == current.id,
            Enrollment.course_id == s.course_id,
        ).first()
        if not existing_enrol:
            db.add(Enrollment(
                user_id=current.id,
                course_id=s.course_id,
                progress=0.0,
            ))
            auto_enrolled = True
    db.commit()
    db.refresh(rsvp)
    return {
        "status": rsvp.status,
        "auto_enrolled": auto_enrolled,
        "course_id": s.course_id if auto_enrolled else None,
    }
