"""Weekly cohort digest.

Composes a single email per organization summarising every cohort's progress:
  - Cohorts that ALREADY hit the celebration threshold (recap).
  - Cohorts WITHIN 15 percentage points of the threshold (predictive nudge —
    "only N more completions to a celebration ping").
  - Other cohorts (compact list).

One email per ADMIN per org per week. Idempotent — `cohort_digest_last_sent_at`
is updated after a successful queue, and the scheduler skips orgs sent within
the past 6 days.

Triggered by:
  - APScheduler cron at Monday 09:00 UTC (see outbox_worker.start_scheduler).
  - Manual button → POST /api/admin/cohort-digest/send-now.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    Certificate, Enrollment, EnrollmentStatus, ExamAttempt,
    Organization, User, UserRole,
)
from services import audit_service
from services.mail_service import MailService

logger = logging.getLogger("ifpi.cohort.digest")

NEAR_THRESHOLD_WINDOW = 15  # percentage points below threshold = "nudge zone"
WEEKLY_DEDUP_DAYS = 6       # don't re-send if sent within this many days


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
    return {
        "cohort": cohort, "learners": len(learner_ids), "enrollments": total,
        "completions": completed, "completion_rate": rate,
        "avg_exam_score": round(avg, 1), "certificates": certs,
    }


def compute_org_digest(db: Session, org: Organization) -> dict:
    """Returns the digest payload: lists of cohorts bucketed by progress.

    Always returns a dict (never None); empty `cohorts` list when the org has
    none yet."""
    threshold = org.cohort_threshold or 75
    cohort_names = [r[0] for r in db.query(User.cohort).filter(
        User.organization_id == org.id,
        User.cohort.isnot(None), User.cohort != "",
    ).distinct().all()]

    all_stats: list[dict] = []
    for name in cohort_names:
        s = _stats_for_cohort(db, org.id, name)
        if s:
            all_stats.append(s)

    past = [s for s in all_stats if s["completion_rate"] >= threshold]
    nudge = [s for s in all_stats
             if s["completion_rate"] < threshold
             and (threshold - s["completion_rate"]) <= NEAR_THRESHOLD_WINDOW]
    other = [s for s in all_stats
             if s["completion_rate"] < threshold
             and (threshold - s["completion_rate"]) > NEAR_THRESHOLD_WINDOW]

    # For nudge cohorts compute "how many more completions to hit threshold"
    for s in nudge:
        target_completions = math.ceil((threshold / 100.0) * s["enrollments"])
        s["needed_completions"] = max(0, target_completions - s["completions"])

    past.sort(key=lambda s: -s["completion_rate"])
    nudge.sort(key=lambda s: -(s["completion_rate"]))
    other.sort(key=lambda s: -s["completion_rate"])

    return {
        "threshold": threshold,
        "past": past,
        "nudge": nudge,
        "other": other,
        "total_cohorts": len(all_stats),
    }


def _bar(pct: float) -> str:
    """ASCII-style progress bar safe in any mail client."""
    width = 20
    filled = min(width, max(0, int(round(pct / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def _render_html(org: Organization, payload: dict) -> str:
    threshold = payload["threshold"]
    past, nudge, other = payload["past"], payload["nudge"], payload["other"]

    def _row(s: dict, accent: str, extra: str = "") -> str:
        return (
            f'<tr><td style="padding:6px 10px;font-family:ui-monospace,monospace;font-size:12px;color:#0f172a">{s["cohort"]}</td>'
            f'<td style="padding:6px 10px;font-family:ui-monospace,monospace;font-size:12px;color:{accent}">{s["completion_rate"]}%</td>'
            f'<td style="padding:6px 10px;font-family:ui-monospace,monospace;font-size:11px;color:#64748b">{_bar(s["completion_rate"])}</td>'
            f'<td style="padding:6px 10px;font-size:12px;color:#475569">{s["completions"]}/{s["enrollments"]} done · avg {s["avg_exam_score"]}% · {s["certificates"]} certs{extra}</td></tr>'
        )

    sections: list[str] = []
    if past:
        rows = "".join(_row(s, "#059669") for s in past)
        sections.append(
            f'<h3 style="margin:18px 0 6px;font:600 14px system-ui;color:#0f172a">🎉 Past the {threshold}% threshold</h3>'
            f'<table style="border-collapse:collapse;width:100%;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:6px">{rows}</table>'
        )
    if nudge:
        rows = "".join(
            _row(s, "#d97706",
                 f' · <strong style="color:#b45309">{s["needed_completions"]} more to celebrate</strong>')
            for s in nudge
        )
        sections.append(
            f'<h3 style="margin:18px 0 6px;font:600 14px system-ui;color:#0f172a">🔥 Within reach (≤ {NEAR_THRESHOLD_WINDOW}pp of threshold)</h3>'
            f'<table style="border-collapse:collapse;width:100%;background:#fffbeb;border:1px solid #fde68a;border-radius:6px">{rows}</table>'
        )
    if other:
        rows = "".join(_row(s, "#475569") for s in other)
        sections.append(
            f'<h3 style="margin:18px 0 6px;font:600 14px system-ui;color:#0f172a">Early progress</h3>'
            f'<table style="border-collapse:collapse;width:100%;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px">{rows}</table>'
        )

    if not sections:
        sections.append(
            '<p style="color:#64748b;font:14px system-ui">No cohorts with enrolments yet — invite learners with a cohort tag to start tracking progress here.</p>'
        )

    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif;max-width:680px;margin:0 auto;padding:24px;background:#fff">'
        f'<h2 style="margin:0 0 6px;font-weight:700;color:#0f172a">Weekly cohort digest</h2>'
        f'<p style="margin:0 0 16px;color:#64748b;font-size:13px">{org.name} · celebration threshold {threshold}%</p>'
        + "".join(sections) +
        '<p style="margin:24px 0 4px;color:#94a3b8;font-size:11px">— sent automatically every Monday by IFPI Learning. '
        'Disable in Settings → Cohort milestone celebrations.</p></div>'
    )


def _admin_emails(db: Session, org_id: int) -> list[User]:
    return db.query(User).join(UserRole).filter(
        User.organization_id == org_id,
        UserRole.role.in_(("ADMIN", "SUPER_ADMIN")),
        User.is_active.is_(True),
    ).all()


def send_digest_for_org(db: Session, org: Organization, *, actor=None) -> int:
    """Queues one email per admin in the org. Returns count queued.

    Updates `cohort_digest_last_sent_at` and writes a `COHORT_DIGEST_SENT`
    audit row. Caller is responsible for committing the session.
    """
    payload = compute_org_digest(db, org)
    admins = _admin_emails(db, org.id)
    if not admins:
        logger.info("Org %s has no active admins — skipping digest", org.slug)
        return 0

    body_html = _render_html(org, payload)
    subject = f"📊 Weekly cohort digest — {org.name} ({payload['total_cohorts']} cohort{'s' if payload['total_cohorts'] != 1 else ''})"

    mail = MailService(db)
    for a in admins:
        mail.send_email(
            organization_id=org.id, to_email=a.email, to_name=a.name, user_id=a.id,
            subject=subject, body_html=body_html, body_text=None,
            template="cohort_digest",
        )

    org.cohort_digest_last_sent_at = datetime.now(timezone.utc)

    class _SystemActor:
        id = getattr(actor, "id", None)
        organization_id = org.id

    audit_service.record(
        db, actor or _SystemActor(), "COHORT_DIGEST_SENT",
        target_type="organization", target_id=str(org.id),
        metadata={
            "actor": "manual" if actor else "system",
            "admin_count": len(admins),
            "cohort_count": payload["total_cohorts"],
            "past": len(payload["past"]),
            "nudge": len(payload["nudge"]),
            "threshold": payload["threshold"],
        },
    )
    return len(admins)


def send_weekly_digests(db: Session) -> int:
    """Loops every org. Skips disabled orgs and those sent within WEEKLY_DEDUP_DAYS.

    Returns total emails queued across all orgs."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=WEEKLY_DEDUP_DAYS)
    total = 0
    orgs = db.query(Organization).filter(
        Organization.cohort_digest_enabled.is_(True),
    ).all()
    for org in orgs:
        last = org.cohort_digest_last_sent_at
        # SQLite stores datetimes naive — coerce for safe compare.
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last > cutoff:
                logger.info("Skipping %s digest — sent at %s", org.slug, last.isoformat())
                continue
        try:
            queued = send_digest_for_org(db, org)
            total += queued
            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("digest failed for %s: %s", org.slug, e)
    return total
