"""Iter 30p — Scheduled reports worker.

Called from the existing APScheduler tick every minute (piggybacks on
outbox_worker). Finds `ScheduledReport` rows where `next_run_at <= now`,
generates the payload, drops HTML into `outbox_messages`, and rolls the
cursor forward.

Report generation delegates to per-kind builders. Each returns
`(subject, html_body)`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from models import (
    Enrollment, EnrollmentStatus, OutboxMessage, ScheduledReport, User,
)

logger = logging.getLogger("ifpi.scheduled_reports")


# ── Report kind builders ──────────────────────────────────────────────


def _build_members_needing_action(db: Session, org_id: int) -> tuple[str, str]:
    """Reuses the exact same query as the dashboard widget."""
    from routers.owner_dashboard import members_needing_action

    class _Stub:
        organization_id = org_id
    payload = members_needing_action(limit=25, current=_Stub(), db=db)
    items = payload["items"]
    if not items:
        return ("Members needing action — all clear",
                "<p style='font:14px system-ui'>🎉 Nobody flagged this period.</p>")
    rows = "".join(
        f'<tr>'
        f'<td style="padding:6px 10px;font-size:12px"><strong>{i["name"]}</strong></td>'
        f'<td style="padding:6px 10px;font-size:11px;color:#e11d48">{i["reason_code"]}</td>'
        f'<td style="padding:6px 10px;font-size:12px;color:#475569">{i["reason"]}</td>'
        f'</tr>'
        for i in items)
    html = (
        f'<h2 style="font:600 18px system-ui;color:#0f172a">Members needing action</h2>'
        f'<p style="font:14px system-ui;color:#475569">'
        f'{len(items)} member(s) flagged as of {datetime.utcnow():%Y-%m-%d}.</p>'
        f'<table style="border-collapse:collapse;width:100%">{rows}</table>'
    )
    return (f"[Report] Members needing action ({len(items)})", html)


def _build_enrollment_summary(db: Session, org_id: int) -> tuple[str, str]:
    total = (db.query(Enrollment).join(User, User.id == Enrollment.user_id)
             .filter(User.organization_id == org_id).count())
    active = (db.query(Enrollment).join(User, User.id == Enrollment.user_id)
              .filter(User.organization_id == org_id,
                      Enrollment.status == EnrollmentStatus.IN_PROGRESS).count())
    done = (db.query(Enrollment).join(User, User.id == Enrollment.user_id)
            .filter(User.organization_id == org_id,
                    Enrollment.status == EnrollmentStatus.COMPLETED).count())
    html = (
        f'<h2 style="font:600 18px system-ui">Enrollment summary</h2>'
        f'<ul style="font:14px system-ui;line-height:1.8">'
        f'<li><strong>Total enrolments:</strong> {total}</li>'
        f'<li><strong>In progress:</strong> {active}</li>'
        f'<li><strong>Completed:</strong> {done}</li></ul>'
    )
    return ("[Report] Enrollment summary", html)


def _build_cohort_progress(db: Session, org_id: int) -> tuple[str, str]:
    from services.cohort_digest import compute_org_digest, _render_html
    from models import Organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return ("[Report] Cohort progress", "<p>Organization not found</p>")
    payload = compute_org_digest(db, org)
    return ("[Report] Cohort progress", _render_html(org, payload))


def _build_certificate_issuance(db: Session, org_id: int) -> tuple[str, str]:
    """How many certificates issued in the last 30 days."""
    from models import Certificate
    cutoff = datetime.utcnow() - timedelta(days=30)
    q = (db.query(Certificate)
         .filter(Certificate.organization_id == org_id,
                 Certificate.issued_at >= cutoff)
         .order_by(Certificate.issued_at.desc()).limit(50))
    rows = list(q.all())
    html = (
        f'<h2 style="font:600 18px system-ui">Certificate issuance — last 30 days</h2>'
        f'<p style="font:14px system-ui">{len(rows)} certificate(s) issued.</p>'
    )
    if rows:
        html += '<ol style="font:13px system-ui">' + "".join(
            f'<li>Cert #{c.id} · issued {c.issued_at:%Y-%m-%d}</li>' for c in rows[:20]
        ) + '</ol>'
    return ("[Report] Certificate issuance", html)


BUILDERS: dict[str, Callable[[Session, int], tuple[str, str]]] = {
    "members_needing_action": _build_members_needing_action,
    "cohort_progress": _build_cohort_progress,
    "certificate_issuance": _build_certificate_issuance,
    "enrollment_summary": _build_enrollment_summary,
}


# ── Enqueue helper ────────────────────────────────────────────────────


def _next_run(cadence: str) -> datetime:
    now = datetime.utcnow()
    return now + ({"daily": timedelta(days=1),
                   "weekly": timedelta(days=7),
                   "monthly": timedelta(days=30)}.get(cadence,
                                                     timedelta(days=7)))


def generate_and_enqueue(db: Session, sched: ScheduledReport) -> bool:
    builder = BUILDERS.get(sched.report_kind)
    if not builder:
        logger.warning("unknown report_kind %s", sched.report_kind)
        return False
    try:
        subject, html = builder(db, sched.organization_id)
    except Exception as e:
        logger.exception("report build failed: %s", e)
        return False

    for recipient in (sched.recipient_emails or []):
        msg = OutboxMessage(
            organization_id=sched.organization_id,
            user_id=sched.created_by_user_id,
            to_email=recipient,
            subject=subject,
            body_html=html,
            template="scheduled_report",
        )
        db.add(msg)

    sched.last_run_at = datetime.utcnow()
    sched.next_run_at = _next_run(sched.cadence)
    db.flush()
    return True


def tick(db: Session) -> int:
    """Called from the outbox_worker scheduler. Runs all due schedules."""
    now = datetime.utcnow()
    due = (db.query(ScheduledReport)
           .filter(ScheduledReport.is_active.is_(True),
                   ScheduledReport.next_run_at <= now).all())
    count = 0
    for row in due:
        try:
            if generate_and_enqueue(db, row):
                count += 1
        except Exception as e:
            logger.exception("tick failed for report %d: %s", row.id, e)
    if count:
        db.commit()
    return count
