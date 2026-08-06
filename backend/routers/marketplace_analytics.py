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
from datetime import date, datetime, timedelta
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
    # We're typically behind a CDN/proxy (Cloudflare + K8s ingress), so
    # `request.client.host` is the proxy's ephemeral IP, which changes
    # between requests. Trust `X-Forwarded-For` (first entry = real
    # client) when present; fall back to direct socket IP otherwise.
    # Iter 26 — Same test-only IP pin as the login/verify limiters.
    import os as _os
    if _os.environ.get("ALLOW_TEST_TOKEN_HEADER") == "true":
        test_ip = request.headers.get("x-test-client-ip") or ""
        if test_ip.strip():
            ua = request.headers.get("user-agent", "")
            h = hashlib.sha256(f"{test_ip.strip()}|{ua}".encode()).hexdigest()[:16]
            return f"a:{h}"
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
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
@admin_router.get("/marketplace-funnel")
def marketplace_funnel_rollup(
    days: int = Query(30, ge=1, le=365),
    top_n: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN", "INSTRUCTOR")),
):
    """Iter 25 — Cross-course marketplace funnel roll-up for the current
    organisation. Aggregates views/enrolments/completions across all
    published courses + returns the top-N by view-to-enrol conversion
    rate."""
    since = date.today() - timedelta(days=days)
    since_iso = since.isoformat()
    since_dt = datetime.combine(since, datetime.min.time())

    # Course ids belonging to this org (any status — completions are
    # still valid on unpublished courses if legacy learners exist)
    org_course_ids = [
        c.id for c in db.query(Course.id).filter(
            Course.organization_id == current.organization_id
        ).all()
    ]
    if not org_course_ids:
        return {"days_window": days, "totals": {"views": 0, "enrollments": 0, "completions": 0},
                "view_to_enroll_rate": 0.0, "enroll_to_complete_rate": 0.0,
                "top_by_conversion": [], "daily": []}

    total_views = db.query(CourseView).filter(
        CourseView.course_id.in_(org_course_ids),
        CourseView.viewed_on_date >= since_iso,
    ).count()
    total_enrolls = db.query(Enrollment).filter(
        Enrollment.course_id.in_(org_course_ids),
        Enrollment.enrolled_at >= since_dt,
    ).count()
    total_completes = db.query(Enrollment).filter(
        Enrollment.course_id.in_(org_course_ids),
        Enrollment.completed_at.isnot(None),
        Enrollment.completed_at >= since_dt,
    ).count()

    view_to_enroll = min(1.0, round(total_enrolls / total_views, 4)) if total_views > 0 else 0.0
    enroll_to_complete = min(1.0, round(total_completes / total_enrolls, 4)) if total_enrolls > 0 else 0.0

    # Per-course numbers → sorted by V→E rate desc
    views_by_course = dict(
        db.query(CourseView.course_id, func.count(CourseView.id))
        .filter(CourseView.course_id.in_(org_course_ids),
                CourseView.viewed_on_date >= since_iso)
        .group_by(CourseView.course_id).all()
    )
    enrolls_by_course = dict(
        db.query(Enrollment.course_id, func.count(Enrollment.id))
        .filter(Enrollment.course_id.in_(org_course_ids),
                Enrollment.enrolled_at >= since_dt)
        .group_by(Enrollment.course_id).all()
    )
    completes_by_course = dict(
        db.query(Enrollment.course_id, func.count(Enrollment.id))
        .filter(Enrollment.course_id.in_(org_course_ids),
                Enrollment.completed_at.isnot(None),
                Enrollment.completed_at >= since_dt)
        .group_by(Enrollment.course_id).all()
    )
    course_titles = {
        c.id: c.title for c in db.query(Course.id, Course.title).filter(
            Course.id.in_(org_course_ids)
        ).all()
    }

    per_course = []
    for cid in org_course_ids:
        v, e, c = views_by_course.get(cid, 0), enrolls_by_course.get(cid, 0), completes_by_course.get(cid, 0)
        if v == 0 and e == 0 and c == 0:
            continue
        per_course.append({
            "course_id": cid,
            "course_title": course_titles.get(cid, "?"),
            "views": v, "enrollments": e, "completions": c,
            "view_to_enroll_rate": min(1.0, round(e / v, 4)) if v > 0 else 0.0,
            "enroll_to_complete_rate": min(1.0, round(c / e, 4)) if e > 0 else 0.0,
        })
    top_by_conversion = sorted(
        [p for p in per_course if p["views"] > 0],
        key=lambda p: p["view_to_enroll_rate"], reverse=True,
    )[:top_n]

    # Daily totals across all org courses
    daily_views = dict(
        db.query(CourseView.viewed_on_date, func.count(CourseView.id))
        .filter(CourseView.course_id.in_(org_course_ids),
                CourseView.viewed_on_date >= since_iso)
        .group_by(CourseView.viewed_on_date).all()
    )
    daily_enrolls = dict(
        db.query(func.date(Enrollment.enrolled_at), func.count(Enrollment.id))
        .filter(Enrollment.course_id.in_(org_course_ids),
                Enrollment.enrolled_at >= since_dt)
        .group_by(func.date(Enrollment.enrolled_at)).all()
    )
    daily_completes = dict(
        db.query(func.date(Enrollment.completed_at), func.count(Enrollment.id))
        .filter(Enrollment.course_id.in_(org_course_ids),
                Enrollment.completed_at.isnot(None),
                Enrollment.completed_at >= since_dt)
        .group_by(func.date(Enrollment.completed_at)).all()
    )
    daily = [{
        "date": (since + timedelta(days=i)).isoformat(),
        "views": daily_views.get((since + timedelta(days=i)).isoformat(), 0),
        "enrollments": daily_enrolls.get((since + timedelta(days=i)).isoformat(), 0),
        "completions": daily_completes.get((since + timedelta(days=i)).isoformat(), 0),
    } for i in range(days + 1)]

    return {
        "days_window": days,
        "totals": {
            "views": total_views,
            "enrollments": total_enrolls,
            "completions": total_completes,
            "courses_with_activity": len(per_course),
        },
        "view_to_enroll_rate": view_to_enroll,
        "enroll_to_complete_rate": enroll_to_complete,
        "top_by_conversion": top_by_conversion,
        "daily": daily,
    }


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

    # Iter 24 — Clamp to [0.0, 1.0]. In real production data, enrollments
    # will often exceed views because view-tracking was only added in
    # this iteration while enrollments have historic backlog. Without
    # the clamp the UI shows nonsense like "350% conversion".
    view_to_enroll = min(1.0, round(enrollments / views, 4)) if views > 0 else 0.0
    enroll_to_complete = min(1.0, round(completions / enrollments, 4)) if enrollments > 0 else 0.0

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



# ── Slide-level drop-off (Iter 26) ───────────────────────────────────
from models import CourseSlide, SlideView  # noqa: E402


@public_router.post("/{course_id}/slides/{slide_id}/track-view", status_code=200)
def track_slide_view(
    course_id: int,
    slide_id: int,
    db: Session = Depends(get_db),
    current: Optional[CurrentUser] = Depends(get_optional_user),
):
    """Iter 26 — Fire once per (slide, learner, day) from the course
    player's slide-change effect. Anonymous viewers are ignored (we
    need a user_id to compute drop-off — anon sessions can't be
    correlated across slides reliably)."""
    if current is None:
        return {"tracked": False, "reason": "anon"}
    # Verify the slide actually belongs to that course
    slide = db.query(CourseSlide).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id
    ).first()
    if not slide:
        return {"tracked": False, "reason": "unknown_slide"}
    today = date.today().isoformat()
    # Iter 38 Phase B — enqueue into progress_outbox instead of inserting
    # SlideView synchronously. Under 10× traffic the direct insert path
    # was ~20% of all request time; the outbox drops it to a tiny
    # single-row INSERT that returns immediately. Background worker
    # (services.outbox_worker._progress_outbox_tick, every 2s) does the
    # actual SlideView insert. SlideView's unique constraint on
    # (slide, user, day) makes the handler safely idempotent.
    from services.progress_outbox import enqueue
    enqueue(db, "slide_view", {
        "course_id": course_id,
        "slide_id": slide_id,
        "user_id": current.id,
        "viewed_on_date": today,
    })
    db.commit()
    return {"tracked": True, "queued": True}


@admin_router.get("/course-dropoff/{course_id}")
def course_dropoff(
    course_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN", "INSTRUCTOR")),
):
    """Iter 26 — Per-slide unique-viewers + drop-off %. For each slide
    in the course, compute how many unique learners viewed it in the
    window, and the drop-off relative to the first slide (which acts
    as the 100% baseline for course-entry)."""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    since_iso = (date.today() - timedelta(days=days)).isoformat()
    # Distinct-user counts per slide
    rows = (
        db.query(SlideView.slide_id, func.count(func.distinct(SlideView.user_id)))
        .filter(SlideView.course_id == course_id,
                SlideView.viewed_on_date >= since_iso)
        .group_by(SlideView.slide_id).all()
    )
    counts = {sid: n for sid, n in rows}

    slides = sorted(
        db.query(CourseSlide).filter(CourseSlide.course_id == course_id).all(),
        key=lambda s: s.order_index,
    )
    if not slides:
        return {"course_id": course_id, "course_title": course.title,
                "days_window": days, "slides": []}

    baseline = counts.get(slides[0].id, 0)  # first slide = 100%
    out = []
    for i, s in enumerate(slides):
        viewers = counts.get(s.id, 0)
        retention = round(viewers / baseline, 4) if baseline > 0 else 0.0
        prev_viewers = counts.get(slides[i - 1].id, 0) if i > 0 else viewers
        step_dropoff = round(1 - (viewers / prev_viewers), 4) if prev_viewers > 0 else 0.0
        out.append({
            "slide_id": s.id,
            "order_index": s.order_index,
            "title": s.title,
            "unique_viewers": viewers,
            "retention": min(1.0, max(0.0, retention)),
            "step_dropoff": min(1.0, max(0.0, step_dropoff)),
        })
    return {
        "course_id": course_id,
        "course_title": course.title,
        "days_window": days,
        "baseline_viewers": baseline,
        "slides": out,
    }

