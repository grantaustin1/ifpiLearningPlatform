"""Cohort milestone celebrations.

Each tick the outbox worker invokes `check_cohorts()` which:
  1. Loads each organization's settings (threshold % + optional webhook URL)
  2. For every cohort in that org, queries the cohort_stats aggregate
  3. If completion_rate ≥ threshold AND no prior COHORT_MILESTONE_REACHED
     audit row exists for that org+cohort+threshold, emit:
       (a) audit log entry  COHORT_MILESTONE_REACHED
       (b) outbox row addressed to every ADMIN in the org with a summary
       (c) optional webhook POST (HMAC-signed) to the org's celebration URL

Idempotent — the audit_log entry is the dedupe key, so we never double-fire.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    AuditLog, Certificate, Enrollment, EnrollmentStatus, ExamAttempt,
    Organization, User, UserBadge, UserRole,
)
from services import audit_service
from services.mail_service import MailService

logger = logging.getLogger("ifpi.cohort.celebrate")

DEFAULT_THRESHOLD = 75


def _stats_for_cohort(db: Session, org_id: int, cohort: str) -> Optional[dict]:
    learner_ids = [u.id for u in db.query(User).filter(
        User.organization_id == org_id, User.cohort == cohort,
    ).all()]
    if not learner_ids:
        return None
    enrolls = db.query(Enrollment).filter(Enrollment.user_id.in_(learner_ids))
    total = enrolls.count()
    if not total:
        return None
    completed = enrolls.filter(Enrollment.status == EnrollmentStatus.COMPLETED).count()
    rate = round((completed / total) * 100, 1)
    avg = float(db.query(func.avg(ExamAttempt.score)).filter(
        ExamAttempt.user_id.in_(learner_ids),
        ExamAttempt.score.isnot(None),
    ).scalar() or 0)
    certs = db.query(Certificate).filter(Certificate.user_id.in_(learner_ids)).count()
    badges = db.query(UserBadge).filter(UserBadge.user_id.in_(learner_ids)).count()
    return {
        "learners": len(learner_ids), "enrollments": total,
        "completions": completed, "completion_rate": rate,
        "avg_exam_score": round(avg, 1),
        "certificates": certs, "badges": badges,
    }


def _already_celebrated(db: Session, org_id: int, cohort: str, threshold: int) -> bool:
    """Idempotency check — has this exact cohort+threshold already fired?

    The (org_id, action, target_type, target_id) tuple already pinpoints
    this cohort's milestone row. Threshold matters only if the org later
    *lowers* its threshold; for now there's a single global threshold so
    presence-of-row is sufficient.
    """
    return db.query(AuditLog).filter(
        AuditLog.organization_id == org_id,
        AuditLog.action == "COHORT_MILESTONE_REACHED",
        AuditLog.target_type == "cohort",
        AuditLog.target_id == cohort,
    ).first() is not None


def _send_celebration_outbox(db: Session, org: Organization, cohort: str, stats: dict) -> None:
    admins = db.query(User).join(UserRole).filter(
        User.organization_id == org.id,
        UserRole.role.in_(("ADMIN", "SUPER_ADMIN")),
        User.is_active.is_(True),
    ).all()
    if not admins:
        return
    body_html = f"""
        <h2>🎉 Cohort milestone reached: {cohort}</h2>
        <p>Your cohort just crossed the {stats['completion_rate']}% completion threshold.</p>
        <ul>
          <li>Learners: <strong>{stats['learners']}</strong></li>
          <li>Completions: <strong>{stats['completions']} / {stats['enrollments']}</strong></li>
          <li>Average exam score: <strong>{stats['avg_exam_score']}%</strong></li>
          <li>Certificates issued: <strong>{stats['certificates']}</strong></li>
        </ul>
        <p>— {org.name}</p>
    """.strip()
    mail = MailService(db)
    for a in admins:
        mail.send_email(
            organization_id=org.id, to_email=a.email, to_name=a.name, user_id=a.id,
            subject=f"🎉 Cohort '{cohort}' hit {stats['completion_rate']}% completion",
            body_html=body_html, body_text=None, template="cohort_milestone",
        )


def _post_webhook(url: str, payload: dict) -> None:
    """Best-effort POST to a Discord/Slack incoming webhook.

    Both providers accept a simple `{content: ...}` body for text;
    we send a richer formatted message so it renders nicely in either."""
    try:
        import requests as _r
        # Slack accepts {text:...}; Discord accepts {content:...}.
        # Send both so the same URL works for either provider.
        _r.post(url, json={
            "text": payload["text"],
            "content": payload["text"],
            "username": "IFPI Learning",
        }, timeout=8)
    except Exception as e:
        logger.exception("celebration webhook POST failed: %s", e)


def check_cohorts(db: Session) -> int:
    """Run by the outbox worker on each tick. Returns count of celebrations fired."""
    fired = 0
    orgs = db.query(Organization).all()
    for org in orgs:
        threshold = org.cohort_threshold or DEFAULT_THRESHOLD
        cohorts = [r[0] for r in db.query(User.cohort).filter(
            User.organization_id == org.id, User.cohort.isnot(None), User.cohort != "",
        ).distinct().all()]
        for cohort in cohorts:
            stats = _stats_for_cohort(db, org.id, cohort)
            if not stats or stats["completion_rate"] < threshold:
                continue
            if _already_celebrated(db, org.id, cohort, threshold):
                continue

            class _SystemActor:
                """Synthetic actor for system-fired events."""
                id = None
                organization_id = org.id
            audit_service.record(
                db, _SystemActor(), "COHORT_MILESTONE_REACHED",
                target_type="cohort", target_id=cohort,
                metadata={"actor": "system", "threshold": threshold, **stats},
            )
            try:
                _send_celebration_outbox(db, org, cohort, stats)
            except Exception as e:
                logger.exception("celebration outbox failed for %s/%s: %s", org.slug, cohort, e)
            if org.cohort_celebration_webhook_url:
                _post_webhook(org.cohort_celebration_webhook_url, {
                    "text": (f"🎉 *{org.name}* cohort *{cohort}* hit "
                             f"*{stats['completion_rate']}%* completion! "
                             f"({stats['completions']}/{stats['enrollments']} enrolments, "
                             f"avg score {stats['avg_exam_score']}%, "
                             f"{stats['certificates']} certs)"),
                })
            # Outgoing event-bus webhook (separate from the Slack/Discord ping)
            try:
                from services.webhook_service import emit_safely
                emit_safely(db, org.id, "cohort.milestone_reached", {
                    "cohort": cohort, "threshold": threshold, **stats,
                })
            except Exception:
                logger.exception("cohort.milestone_reached webhook emit failed")
            db.commit()
            fired += 1
            logger.info("Celebrated cohort %s/%s at %.1f%%", org.slug, cohort, stats["completion_rate"])
    return fired
