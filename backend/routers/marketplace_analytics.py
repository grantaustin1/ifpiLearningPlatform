"""Iter 24 — Marketplace funnel analytics.

Endpoints:
- POST /api/catalog/{course_id}/track-view   (public, no auth)
    Records a marketplace impression. Dedup by (course_id, viewer_key,
    day). Returns a lightweight ack.
- GET  /api/admin/marketplace-funnel/{course_id}   (admin)
    Returns the funnel numbers for one course:
        {views, enrollments, completions,
         view_to_enroll_rate, enroll_to_complete_rate,
         daily: [{date, views, enrollments, completions}, ...]}

Design notes:
- View recording is fire-and-forget from the frontend (a POST from the
  detail-page useEffect). We swallow errors and return 200 so a slow
  DB doesn't break the marketplace UX.
- Anon viewer_key = SHA-256(IP + UA)[:16] — enough entropy to keep
  distinct anons distinct across a day, but truncated so it can't be
  reversed into PII.
- Rates are float in [0.0, 1.0]. Division-by-zero → 0.0.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_optional_user, requires_roles
from core.database import get_db
from models import Course, CourseStatus, CourseView, Enrollment, Organization

logger = logging.getLogger(__name__)

public_router = APIRouter(prefix="/api/catalog", tags=["Marketplace Analytics"])
admin_router = APIRouter(prefix="/api/admin", tags=["Marketplace Analytics"])


# ── Public: track view ───────────────────────────────────────────────
class TrackViewIn(BaseModel):
    referrer: Optional[str] = None


def _viewer_key(request: Request, user_id: Optional[int]) -> str:
    if user_id is not None:
        return f"u:{user_id}"
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    h = hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:16]
    return f"a:{h}"


@public_router.post("/{course_id}/track-view", status_code=200)
def track_view(
    course_id: int,
    body: TrackViewIn,
    request: Request,
    db: Session = Depends(get_db),
    current: Optional[CurrentUser] = Depends(get_optional_user),
):
    # Ensure the course is in a publicly listable state — silently drop
    # otherwise (no need to leak private-course existence to anons).
    course = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.id == course_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .first()
    )
    if not course:
        return {"tracked": False}

    uid = current.id if current else None
    key = _viewer_key(request, uid)
    today = date.today().isoformat()

    view = CourseView(
        course_id=course_id, viewer_key=key, user_id=uid,
        referrer=(body.referrer or None), viewed_on_date=today,
    )
    try:
        db.add(view); db.commit()
        return {"tracked": True}
    except IntegrityError:
        # Dedup collision → already counted today for this viewer. That's fine.
        db.rollback()
        return {"tracked": False, "reason": "already_counted_today"}


# ── Admin: per-course funnel ─────────────────────────────────────────
@admin_router.get("/marketplace-funnel/{course_id}")
def marketplace_funnel(
    course_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN", "INSTRUCTOR")),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    since = date.today() - timedelta(days=days)
    since_iso = since.isoformat()

    views = db.query(CourseView).filter(
        CourseView.course_id == course_id,
        CourseView.viewed_on_date >= since_iso,
    ).count()

    enrollments = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.enrolled_at >= datetime.combine(since, datetime.min.time()),
    ).count()

    completions = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.completed_at.isnot(None),
        Enrollment.completed_at >= datetime.combine(since, datetime.min.time()),
    ).count()

    view_to_enroll = round(enrollments / views, 4) if views > 0 else 0.0
    enroll_to_complete = round(completions / enrollments, 4) if enrollments > 0 else 0.0

    # Daily breakdown — GROUP BY viewed_on_date. Enrollments and completions
    # are grouped by DATE(enrolled_at/completed_at). SQLite `date()` function
    # is used explicitly for cross-dialect safety.
    daily_views = dict(
        db.query(CourseView.viewed_on_date, func.count(CourseView.id))
        .filter(CourseView.course_id == course_id,
                CourseView.viewed_on_date >= since_iso)
        .group_by(CourseView.viewed_on_date).all()
    )
    daily_enrolls = dict(
        db.query(func.date(Enrollment.enrolled_at), func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id,
                Enrollment.enrolled_at >= datetime.combine(since, datetime.min.time()))
        .group_by(func.date(Enrollment.enrolled_at)).all()
    )
    daily_completes = dict(
        db.query(func.date(Enrollment.completed_at), func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id,
                Enrollment.completed_at.isnot(None),
                Enrollment.completed_at >= datetime.combine(since, datetime.min.time()))
        .group_by(func.date(Enrollment.completed_at)).all()
    )

    daily = []
    for i in range(days + 1):
        d = (since + timedelta(days=i)).isoformat()
        daily.append({
            "date": d,
            "views": daily_views.get(d, 0),
            "enrollments": daily_enrolls.get(d, 0),
            "completions": daily_completes.get(d, 0),
        })

    return {
        "course_id": course_id,
        "course_title": course.title,
        "days_window": days,
        "views": views,
        "enrollments": enrollments,
        "completions": completions,
        "view_to_enroll_rate": view_to_enroll,
        "enroll_to_complete_rate": enroll_to_complete,
        "daily": daily,
    }
