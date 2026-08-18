"""Admin analytics overview routes — includes audit log, cohorts, leaderboard, digest."""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, selectinload

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import (
    AuditLog, Certificate, Course, Enrollment, EnrollmentStatus, Exam,
    ExamAttempt, Organization, User, UserBadge,
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
    from core.cache import cache_get, cache_set
    _ck = f"analytics:{org}"
    _hit = cache_get(_ck)
    if _hit is not None:
        return _hit
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

    from collections import OrderedDict
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


# ── Audit log (migrated from iter8.py) ───────────────────────────────
@admin_router.get("/audit-log")
def list_audit(
    actor: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    q = db.query(AuditLog).filter(AuditLog.organization_id == current.organization_id)
    if actor is not None:
        q = q.filter(AuditLog.actor_user_id == actor)
    if action:
        q = q.filter(AuditLog.action == action.upper())
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    actor_ids = {r.actor_user_id for r in rows if r.actor_user_id}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()}
    return {
        "total": total,
        "items": [{
            "id": r.id, "action": r.action,
            "target_type": r.target_type, "target_id": r.target_id,
            "metadata": r.audit_metadata or {},
            "ip_address": r.ip_address,
            "actor": {"id": r.actor_user_id, "email": users[r.actor_user_id].email,
                      "name": users[r.actor_user_id].name} if r.actor_user_id in users else None,
            "created_at": r.created_at,
        } for r in rows],
    }


# ── Cohorts (migrated from iter8.py) ─────────────────────────────────
@admin_router.get("/cohorts")
def list_cohorts(db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Distinct cohort labels with learner counts."""
    rows = db.query(User.cohort, func.count(User.id)).filter(
        User.organization_id == current.organization_id,
        User.cohort.isnot(None),
        User.cohort != "",
    ).group_by(User.cohort).all()
    return [{"cohort": r[0], "learner_count": r[1]} for r in rows]


@admin_router.get("/reports/cohort-stats")
def cohort_stats(
    cohort: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Completion / exam-score / time-to-graduation for a cohort."""
    base = db.query(User).filter(User.organization_id == current.organization_id)
    if cohort:
        base = base.filter(User.cohort == cohort)
    user_ids = [u.id for u in base.all()]
    if not user_ids:
        return {"cohort": cohort, "learners": 0, "enrollments": 0, "completions": 0,
                "completion_rate": 0, "avg_exam_score": 0, "certificates_issued": 0,
                "badges_earned": 0}
    enrollments = db.query(Enrollment).filter(Enrollment.user_id.in_(user_ids))
    total_enr = enrollments.count()
    completed = enrollments.filter(Enrollment.status == EnrollmentStatus.COMPLETED).count()
    avg_score = db.query(func.avg(ExamAttempt.score)).filter(
        ExamAttempt.user_id.in_(user_ids),
        ExamAttempt.score.isnot(None),
    ).scalar() or 0
    certs = db.query(Certificate).filter(Certificate.user_id.in_(user_ids)).count()
    badges = db.query(UserBadge).filter(UserBadge.user_id.in_(user_ids)).count()
    return {
        "cohort": cohort, "learners": len(user_ids),
        "enrollments": total_enr, "completions": completed,
        "completion_rate": round((completed / total_enr) * 100, 1) if total_enr else 0,
        "avg_exam_score": round(float(avg_score), 1),
        "certificates_issued": certs, "badges_earned": badges,
    }


# ── Leaderboard CSV (migrated from iter8.py) ─────────────────────────
@admin_router.get("/leaderboard.csv")
def leaderboard_csv(cohort: Optional[str] = None,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    q = db.query(User).filter(
        User.organization_id == current.organization_id, User.is_active.is_(True),
    )
    if cohort:
        q = q.filter(User.cohort == cohort)
    rows = q.order_by(User.points.desc().nullslast()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "name", "email", "cohort", "xp", "badges_earned", "certificates"])
    for i, u in enumerate(rows, 1):
        badges = db.query(UserBadge).filter(UserBadge.user_id == u.id).count()
        certs = db.query(Certificate).filter(Certificate.user_id == u.id).count()
        w.writerow([i, u.name or "", u.email, u.cohort or "", u.points or 0, badges, certs])
    name = f"leaderboard{'_' + cohort if cohort else ''}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )


# ── Audit digest (migrated from iter8.py) ────────────────────────────
@admin_router.get("/audit-digest")
async def audit_digest(
    days: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """LLM-generated plain-English summary of the last N days of admin activity."""
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    from sqlalchemy import func as _func
    action_counts = (db.query(AuditLog.action, _func.count(AuditLog.id))
                     .filter(AuditLog.organization_id == current.organization_id,
                             AuditLog.created_at >= since)
                     .group_by(AuditLog.action)
                     .all())
    by_action: dict[str, int] = {a: n for a, n in action_counts}
    total_rows = sum(by_action.values())
    rows = (db.query(AuditLog)
            .filter(AuditLog.organization_id == current.organization_id,
                    AuditLog.created_at >= since)
            .order_by(AuditLog.created_at.desc())
            .limit(300).all())
    deterministic = (
        f"In the last {days} days: {total_rows} admin action(s) recorded."
        + ((" "
            + ", ".join(f"{k.replace('_', ' ').title()}: {v}"
                        for k, v in sorted(by_action.items(), key=lambda kv: -kv[1])[:6])
            + ".") if by_action else " No admin activity to summarise.")
    )
    digest = deterministic
    if rows:
        try:
            from core.config import settings
            if settings.emergent_llm_key:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                import uuid as _uuid
                lines = "\n".join(
                    f"- {r.created_at:%Y-%m-%d}  {r.action}  {r.target_type or ''}#{r.target_id or ''}  meta={r.audit_metadata}"
                    for r in rows[:80]
                )
                chat = LlmChat(api_key=settings.emergent_llm_key,
                               session_id=f"digest-{_uuid.uuid4().hex}",
                               system_message="You produce concise, executive-friendly summaries of admin activity. 3-5 sentences, plain English, no jargon, no markdown.").with_model(
                    settings.ai_builder_provider, settings.ai_builder_model)
                resp = await chat.send_message(UserMessage(
                    text=f"Summarise the last {days} days of admin activity for an "
                         f"IFPI Learning academy. Counts: {by_action}\n\nRaw rows:\n{lines}"))
                digest = (resp if isinstance(resp, str) else getattr(resp, "content", str(resp))).strip()
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("ifpi.audit_digest").exception("digest LLM call failed: %s", e)
            digest = deterministic + " (AI summary unavailable — see logs.)"
    return {
        "days": days, "total_actions": len(rows),
        "counts_by_action": by_action,
        "summary": digest,
    }
