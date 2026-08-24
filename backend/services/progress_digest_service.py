"""Weekly learner progress digest — keeps momentum going.

Runs every Monday (scheduler tick in outbox_worker). For each active
learner with in-progress pathway/course enrollments, queues one summary
email through the standard MailService/outbox pipeline. Idempotent via
an outbox lookback (skips users mailed a digest in the past 6 days).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import (
    Course, Enrollment, LearningPath, LearningPathEnrollment,
    Organization, OutboxMessage, User,
)
from models._common import EnrollmentStatus, OrganizationStatus

logger = logging.getLogger(__name__)

TEMPLATE = "progress_digest"


def _bar(pct: float) -> str:
    pct = max(0, min(100, round(pct)))
    return (
        f'<div style="background:#e2e8f0;border-radius:6px;height:10px;width:100%;max-width:320px;">'
        f'<div style="background:#6366f1;border-radius:6px;height:10px;width:{pct}%;"></div></div>'
    )


def _recently_sent(db: Session, user_id: int, now) -> bool:
    return db.query(OutboxMessage.id).filter(
        OutboxMessage.user_id == user_id,
        OutboxMessage.template == TEMPLATE,
        OutboxMessage.created_at >= now - timedelta(days=6),
    ).first() is not None


def run_progress_digest(db: Session, org_id: int | None = None) -> int:
    """Queue one weekly progress email per active learner. Returns count."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    week_ago = now - timedelta(days=7)
    q = db.query(Organization).filter(
        Organization.status == OrganizationStatus.ACTIVE)
    if org_id:
        q = q.filter(Organization.id == org_id)
    sent = 0
    for org in q.all():
        # Pathway progress per user
        paths = (db.query(LearningPathEnrollment, LearningPath, User)
                 .join(LearningPath, LearningPath.id == LearningPathEnrollment.path_id)
                 .join(User, User.id == LearningPathEnrollment.user_id)
                 .filter(LearningPath.organization_id == org.id)
                 .all())
        # In-progress course enrollments per user
        courses = (db.query(Enrollment, Course, User)
                   .join(Course, Course.id == Enrollment.course_id)
                   .join(User, User.id == Enrollment.user_id)
                   .filter(Course.organization_id == org.id)
                   .all())
        by_user: dict[int, dict] = {}
        for enr, path, user in paths:
            d = by_user.setdefault(user.id, {"user": user, "paths": [], "courses": [], "completed_week": 0})
            d["paths"].append((path.title, enr.progress or 0.0, enr.status))
        for enr, course, user in courses:
            d = by_user.setdefault(user.id, {"user": user, "paths": [], "courses": [], "completed_week": 0})
            if enr.status == EnrollmentStatus.COMPLETED:
                if enr.completed_at and enr.completed_at >= week_ago:
                    d["completed_week"] += 1
            elif (enr.progress or 0) > 0:
                d["courses"].append((course.title, enr.progress or 0.0))

        from services.mail_service import MailService
        mail = MailService(db)
        for uid, d in by_user.items():
            user = d["user"]
            email = (user.email or "").lower()
            if not email or email.endswith(".local") or "migration@" in email:
                continue
            active_paths = [p for p in d["paths"] if p[2] != EnrollmentStatus.COMPLETED]
            if not active_paths and not d["courses"]:
                continue  # nothing in progress — no nag
            if _recently_sent(db, uid, now):
                continue
            name = (user.name or "there").split(" ")[0]
            rows = []
            for title, prog, _st in active_paths:
                rows.append(f'<p style="margin:14px 0 4px;font-weight:600;">{title} — {round(prog)}%</p>{_bar(prog)}')
            for title, prog in d["courses"][:5]:
                rows.append(f'<p style="margin:14px 0 4px;">{title} — {round(prog)}%</p>{_bar(prog)}')
            wins = (f"<p>🎉 You completed <strong>{d['completed_week']}</strong> course"
                    f"{'s' if d['completed_week'] != 1 else ''} this week — great work!</p>"
                    if d["completed_week"] else "")
            body_html = (
                f"<p>Hi {name},</p>"
                f"<p>Here's your weekly progress at {org.name}:</p>"
                f"{wins}{''.join(rows)}"
                f"<p style='margin-top:18px;'>A few minutes today keeps your streak alive — jump back in!</p>"
            )
            body_text = f"Hi {name}, your weekly progress at {org.name}: " + "; ".join(
                f"{t} {round(p)}%" for t, p, *_ in active_paths + d["courses"])
            try:
                mail.send_email(
                    to_email=user.email, to_name=user.name,
                    subject=f"Your weekly progress at {org.name}",
                    body_html=body_html, body_text=body_text,
                    template=TEMPLATE, organization_id=org.id, user_id=uid)
                sent += 1
            except Exception as ex:
                logger.warning("Progress digest failed for %s: %s", user.email, ex)
        db.commit()
    return sent
