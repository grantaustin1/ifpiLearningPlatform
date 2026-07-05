"""Iter 30k — "Members needing action" widget.

Surfaces learners who need attention on the admin dashboard so owners
can proactively re-engage them instead of only reacting to churn.

Categories (ordered by urgency, high → low):
1. **Stalled**    — enrolled ≥ 14 days, progress = 0
2. **Idle mid-course** — progress 1-99%, no activity in 14 days (fallback:
   compare `enrolled_at` since Enrollment has no updated_at column)
3. **Never signed in** — account created ≥ 7 days ago, `last_login_at` is NULL

Every action item includes a reason code, a human message, and an
optional "next step" URL the admin can nudge them with.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from models import Course, Enrollment, EnrollmentStatus, User

router = APIRouter(prefix="/api/admin/dashboard", tags=["Owner Dashboard"])


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


@router.get("/members-needing-action")
def members_needing_action(
    limit: int = Query(20, ge=1, le=100),
    current: CurrentUser = Depends(requires_admin()),
    db: Session = Depends(get_db),
) -> dict:
    # DB stores naive UTC datetimes (SQLite); use naive `now` for arithmetic
    # but return timezone-aware ISO strings.
    now = datetime.utcnow()
    now_iso = datetime.now(timezone.utc).isoformat()
    stall_cutoff = now - timedelta(days=14)
    signup_cutoff = now - timedelta(days=7)

    org_id = current.organization_id
    items: List[dict] = []
    seen_users: set[int] = set()

    # 1) Stalled — enrolled ≥14d ago, progress==0 (highest urgency)
    stalled_q = (
        db.query(Enrollment, User, Course)
        .join(User, User.id == Enrollment.user_id)
        .join(Course, Course.id == Enrollment.course_id)
        .filter(
            User.organization_id == org_id,
            Enrollment.status == EnrollmentStatus.IN_PROGRESS,
            Enrollment.enrolled_at <= stall_cutoff,
            (Enrollment.progress == 0.0) | (Enrollment.progress.is_(None)),
        )
        .order_by(Enrollment.enrolled_at.asc())
        .limit(limit * 3)
    )
    for enrol, u, c in stalled_q.all():
        if u.id in seen_users:
            continue
        seen_users.add(u.id)
        days = (now - enrol.enrolled_at).days
        items.append({
            "user_id": u.id, "email": u.email,
            "name": u.name or u.email.split("@")[0],
            "reason_code": "STALLED",
            "reason": f"Stalled on \u201C{c.title}\u201D",
            "detail": f"Enrolled {days} days ago, 0% progress",
            "next_step": {"label": "Nudge learner",
                          "path": f"/users?nudge={u.id}&course={c.id}"},
            "priority": 1,
        })

    # 2) Idle mid-course — progress 1-99, enrolled ≥14d ago (no updated_at
    #    on Enrollment, so `enrolled_at` is the best signal we have)
    idle_q = (
        db.query(Enrollment, User, Course)
        .join(User, User.id == Enrollment.user_id)
        .join(Course, Course.id == Enrollment.course_id)
        .filter(
            User.organization_id == org_id,
            Enrollment.status == EnrollmentStatus.IN_PROGRESS,
            Enrollment.enrolled_at <= stall_cutoff,
            Enrollment.progress > 0.0,
            Enrollment.progress < 100.0,
        )
        .order_by(Enrollment.enrolled_at.asc())
        .limit(limit * 3)
    )
    for enrol, u, c in idle_q.all():
        if u.id in seen_users:
            continue
        seen_users.add(u.id)
        days = (now - enrol.enrolled_at).days
        pct = int(enrol.progress or 0)
        items.append({
            "user_id": u.id, "email": u.email,
            "name": u.name or u.email.split("@")[0],
            "reason_code": "IDLE",
            "reason": f"Idle mid-course on \u201C{c.title}\u201D ({pct}%)",
            "detail": f"Enrolled {days} days ago",
            "next_step": {"label": "Send reminder",
                          "path": f"/users?nudge={u.id}&course={c.id}"},
            "priority": 2,
        })

    # 3) Never signed in — active account, ≥7d old, no last_login_at
    never_logged_in = (
        db.query(User)
        .filter(
            User.organization_id == org_id,
            User.is_active.is_(True),
            User.last_login_at.is_(None),
            User.created_at <= signup_cutoff,
        )
        .order_by(User.created_at.desc())
        .limit(limit * 2)
        .all()
    )
    for u in never_logged_in:
        if u.id in seen_users:
            continue
        seen_users.add(u.id)
        items.append({
            "user_id": u.id, "email": u.email,
            "name": u.name or u.email.split("@")[0],
            "reason_code": "NEVER_SIGNED_IN",
            "reason": "Invited but never signed in",
            "detail": f"Account created {(now - u.created_at).days} days ago",
            "next_step": {"label": "Resend invite",
                          "path": f"/users?resend={u.id}"},
            "priority": 3,
        })

    items.sort(key=lambda x: (x["priority"], -x["user_id"]))
    return {
        "count": len(items[:limit]),
        "total_flagged": len(items),
        "generated_at": now_iso,
        "items": items[:limit],
    }
