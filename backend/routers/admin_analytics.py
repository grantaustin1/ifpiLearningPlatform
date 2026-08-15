"""Admin analytics overview routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, selectinload

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import (
    Certificate, Course, Enrollment, EnrollmentStatus, Exam,
    ExamAttempt, User,
)
from schemas import (
    AnalyticsOverview,
)

logger = logging.getLogger(__name__)



# ── Analytics (admin) ────────────────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])


@admin_router.get("/analytics/enrollments-weekly")
def enrollments_weekly(weeks: int = Query(12, ge=4, le=26),
                       metric: str = Query("enrollments"),
                       db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Enrolments or completions per ISO week (Iter 43/44 dashboard chart)."""
    from datetime import datetime, timedelta, timezone
    if metric not in ("enrollments", "completions"):
        raise HTTPException(status_code=422, detail="metric must be enrollments or completions")
    ts_col = Enrollment.completed_at if metric == "completions" else Enrollment.enrolled_at
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    start = monday - timedelta(weeks=weeks - 1)
    rows = (db.query(ts_col)
            .join(Course, Course.id == Enrollment.course_id)
            .filter(Course.organization_id == current.organization_id,
                    ts_col >= start.replace(tzinfo=None))
            .all())
    buckets = {(start + timedelta(weeks=i)).date().isoformat(): 0 for i in range(weeks)}
    for (ts,) in rows:
        if ts is None:
            continue
        d = ts if ts.tzinfo is None else ts.replace(tzinfo=None)
        wk = (d - timedelta(days=d.weekday())).date().isoformat()
        if wk in buckets:
            buckets[wk] += 1
    return {"weeks": [{"week_start": k, "count": v} for k, v in buckets.items()]}


@admin_router.get("/analytics", response_model=AnalyticsOverview)
def analytics(db: Session = Depends(get_db),
              current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    org = current.organization_id
    total_learners = db.query(User).filter(User.organization_id == org).count()
    total_courses = db.query(Course).filter(Course.organization_id == org).count()
    total_enrollments = db.query(Enrollment).join(Course).filter(Course.organization_id == org).count()
    completed = db.query(Enrollment).join(Course).filter(
        Course.organization_id == org, Enrollment.status == EnrollmentStatus.COMPLETED,
    ).count()
    completion_rate = round((completed / total_enrollments) * 100) if total_enrollments else 0
    total_certificates = db.query(Certificate).join(User).filter(User.organization_id == org).count()

    attempts = db.query(ExamAttempt).join(Exam).filter(Exam.organization_id == org).all()
    avg_score = round(sum(a.score for a in attempts) / len(attempts)) if attempts else 0

    # Monthly enrollments — last 6 months via Python (DB-agnostic; avoids DATE_TRUNC)
    from collections import OrderedDict
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    months = OrderedDict()
    for i in range(5, -1, -1):
        y = now.year + ((now.month - i - 1) // 12)
        m = ((now.month - i - 1) % 12) + 1
        months[f"{y}-{m:02d}"] = 0
    enrolls = db.query(Enrollment).join(Course).filter(Course.organization_id == org).all()
    for e in enrolls:
        key = f"{e.enrolled_at.year}-{e.enrolled_at.month:02d}"
        if key in months:
            months[key] += 1
    monthly = [{"month": k, "count": v} for k, v in months.items()]

    # Top courses by enrolment
    top_q = db.query(Course, func.count(Enrollment.id).label("c")).outerjoin(Enrollment).filter(
        Course.organization_id == org,
    ).group_by(Course.id).order_by(desc("c")).limit(8).all()
    top_courses = []
    for c, total in top_q:
        comp = sum(1 for e in c.enrollments if e.status == EnrollmentStatus.COMPLETED)
        top_courses.append({
            "id": c.id, "title": c.title, "total": total,
            "completed": comp,
            "rate": round((comp / total) * 100) if total else 0,
        })

    recents = db.query(Enrollment).join(Course).filter(
        Course.organization_id == org,
    ).order_by(desc(Enrollment.enrolled_at)).limit(8).all()
    recent_activity = [{
        "user_name": e.user.name or "Learner", "course_title": e.course.title,
        "status": e.status.value, "progress": e.progress,
        "enrolled_at": e.enrolled_at,
    } for e in recents]

    return AnalyticsOverview(
        total_learners=total_learners, total_courses=total_courses,
        total_enrollments=total_enrollments, completion_rate=completion_rate,
        total_certificates=total_certificates,
        total_exam_attempts=len(attempts), avg_exam_score=avg_score,
        monthly_enrollments=monthly, top_courses=top_courses,
        recent_activity=recent_activity,
    )


@admin_router.get("/users")
def list_users(response: Response,
               db: Session = Depends(get_db),
               limit: int = 200,
               offset: int = 0,
               current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    # Iter 38 — was 1542 queries via lazy-load of user_roles/enrollments/
    # certificates for each user. `selectinload` collapses this to 4 SQL
    # statements total (1 for users + 1 per relationship, regardless of
    # user count). Added pagination via query params + response headers
    # (Github/Stripe convention) so the list-shaped body stays
    # backwards-compatible with existing frontend consumers.
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    q = (db.query(User)
         .options(
             selectinload(User.user_roles),
             selectinload(User.enrollments),
             selectinload(User.certificates),
         )
         .filter(User.organization_id == current.organization_id)
         .order_by(User.created_at.desc()))
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    return [{
        "id": u.id, "email": u.email, "name": u.name,
        "roles": [ur.role for ur in u.user_roles],
        "points": u.points or 0, "enrollments": len(u.enrollments),
        "completed": sum(1 for e in u.enrollments if e.status == EnrollmentStatus.COMPLETED),
        "certificates": len(u.certificates), "created_at": u.created_at,
        "is_active": u.is_active,
    } for u in rows]


