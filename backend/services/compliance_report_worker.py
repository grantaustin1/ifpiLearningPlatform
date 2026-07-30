"""Iter 31 — Certificate revocation compliance auto-report.

Sends a periodic (daily / weekly / monthly — env-configurable) email
summarising all certificate REVOKE + UNREVOKE actions across every
organisation to a single compliance officer address. Designed for
regulated academies (fitness certification bodies, RTOs) who need an audit
trail delivered proactively rather than pulled from the admin UI.

Configuration (backend/.env):
    COMPLIANCE_OFFICER_EMAIL   — recipient. When empty, worker is a no-op.
    COMPLIANCE_REPORT_CADENCE  — daily | weekly | monthly. Default weekly.

Cadence controls the *look-back window* + how often the scheduler
fires this worker. Scheduling is set in outbox_worker.start_scheduler.

Idempotency: relies on the cadence-aligned schedule (no
per-invocation dedup DB flag needed). If a pod restarts mid-window
the worker won't fire twice — APScheduler cron misses that align to
the same window aren't replayed.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from core.database import SessionLocal
from models import Certificate, CertificateRevocationEvent, Organization, User
from services.mail_service import MailService

logger = logging.getLogger(__name__)


CADENCE_WINDOWS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


def _cadence() -> str:
    val = (os.environ.get("COMPLIANCE_REPORT_CADENCE") or "weekly").strip().lower()
    return val if val in CADENCE_WINDOWS else "weekly"


def _recipient() -> str | None:
    val = (os.environ.get("COMPLIANCE_OFFICER_EMAIL") or "").strip()
    return val or None


def _fetch_events(db, since):
    """Return list of (event, cert, user, actor, org) tuples in-window."""
    events = db.query(CertificateRevocationEvent).filter(
        CertificateRevocationEvent.occurred_at >= since
    ).order_by(CertificateRevocationEvent.occurred_at.desc()).all()
    if not events:
        return []
    cert_ids = list({e.certificate_id for e in events})
    actor_ids = list({e.actor_user_id for e in events})
    certs = {c.id: c for c in db.query(Certificate).filter(
        Certificate.id.in_(cert_ids)).all()}
    holder_ids = list({c.user_id for c in certs.values()})
    users = {u.id: u for u in db.query(User).filter(
        User.id.in_(holder_ids + actor_ids)).all()}
    org_ids = list({u.organization_id for u in users.values() if u.organization_id})
    orgs = {o.id: o for o in db.query(Organization).filter(
        Organization.id.in_(org_ids)).all()} if org_ids else {}
    out = []
    for e in events:
        c = certs.get(e.certificate_id)
        if not c:
            continue
        u = users.get(c.user_id)
        a = users.get(e.actor_user_id)
        org = orgs.get(u.organization_id) if u else None
        out.append((e, c, u, a, org))
    return out


def _render(events: list, cadence: str, since) -> tuple[str, str, str]:
    """Return (subject, html, text). Empty when no events."""
    n_rev = sum(1 for (e, *_r) in events if e.action == "REVOKE")
    n_unrev = sum(1 for (e, *_r) in events if e.action == "UNREVOKE")
    subject = (f"Certificate compliance report — {cadence} · "
               f"{n_rev} revoked, {n_unrev} restored")

    rows_html = []
    rows_text = []
    for (e, c, u, a, org) in events:
        holder = (u.name or u.email or f"user #{c.user_id}") if u else f"user #{c.user_id}"
        actor = (a.name or a.email or f"user #{e.actor_user_id}") if a else f"user #{e.actor_user_id}"
        org_name = org.name if org else "—"
        action_style = ("background:#fee2e2;color:#991b1b" if e.action == "REVOKE"
                        else "background:#d1fae5;color:#065f46")
        rows_html.append(
            f"<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;'>"
            f"<span style='{action_style};padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600;'>"
            f"{e.action}</span></td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;'>{holder}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;'>"
            f"<code style='font-size:11px;color:#64748b'>{c.code[:12]}…</code></td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;'>{org_name}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;color:#64748b;font-size:12px;'>{actor}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;color:#64748b;font-size:12px;'>{(e.reason or '—')[:80]}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #f1f5f9;color:#94a3b8;font-size:11px;'>{e.occurred_at.strftime('%Y-%m-%d %H:%M UTC')}</td>"
            f"</tr>"
        )
        rows_text.append(
            f"  [{e.action}] {holder} · cert {c.code[:12]} · org {org_name} · "
            f"by {actor} · reason: {e.reason or '—'} · {e.occurred_at.isoformat()}"
        )
    html = (
        f"<h2 style='margin-top:0'>Certificate Compliance Report</h2>"
        f"<p style='color:#475569;'>"
        f"{cadence.capitalize()} audit covering activity since "
        f"<strong>{since.strftime('%Y-%m-%d %H:%M UTC')}</strong>.</p>"
        f"<p><strong style='color:#dc2626'>{n_rev} revocations</strong> · "
        f"<strong style='color:#059669'>{n_unrev} restorations</strong></p>"
        f"<table style='border-collapse:collapse;font-family:system-ui,sans-serif;font-size:13px;width:100%;'>"
        f"<thead><tr style='background:#f8fafc;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;'>"
        f"<th style='padding:8px 10px'>Action</th>"
        f"<th style='padding:8px 10px'>Learner</th>"
        f"<th style='padding:8px 10px'>Cert</th>"
        f"<th style='padding:8px 10px'>Organisation</th>"
        f"<th style='padding:8px 10px'>Actor</th>"
        f"<th style='padding:8px 10px'>Reason</th>"
        f"<th style='padding:8px 10px'>When</th>"
        f"</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
        + "<p style='color:#94a3b8;font-size:12px;margin-top:20px;'>"
        "Sent by the IFPI Learning compliance auto-report. Configure via "
        "COMPLIANCE_OFFICER_EMAIL + COMPLIANCE_REPORT_CADENCE.</p>"
    )
    text = (
        f"Certificate Compliance Report ({cadence})\n"
        f"Since: {since.isoformat()}\n"
        f"{n_rev} revocations · {n_unrev} restorations\n\n"
        + "\n".join(rows_text)
    )
    return subject, html, text


def run_compliance_report_pass() -> dict:
    """One pass. Returns stats dict.

    - No-op if COMPLIANCE_OFFICER_EMAIL is unset (returns {'sent': 0, 'reason': 'no_recipient'}).
    - Uses the cadence env var to size the look-back window.
    - Even when there are 0 events, we still send an "all quiet" report
      so the compliance officer knows the system is alive (heartbeat).
    """
    to_email = _recipient()
    if not to_email:
        return {"sent": 0, "reason": "no_recipient"}
    cadence = _cadence()
    window = CADENCE_WINDOWS[cadence]
    since = datetime.now(timezone.utc) - window
    db = SessionLocal()
    try:
        events = _fetch_events(db, since)
        subject, html, text = _render(events, cadence, since)
        MailService(db).send_email(
            to_email=to_email, to_name="Compliance Officer",
            subject=subject, body_html=html, body_text=text,
            template="cert_compliance_report",
            organization_id=None, user_id=None,
        )
        db.commit()
        return {"sent": 1, "events": len(events), "cadence": cadence,
                "since": since.isoformat()}
    except Exception as e:  # pragma: no cover
        logger.exception("compliance-report pass failed: %s", e)
        db.rollback()
        return {"sent": 0, "error": str(e)[:200]}
    finally:
        db.close()


def _tick() -> None:  # scheduler entrypoint
    try:
        stats = run_compliance_report_pass()
        if stats.get("sent", 0) > 0:
            logger.info("compliance-report: %s", stats)
    except Exception as e:  # pragma: no cover
        logger.exception("compliance-report tick failed: %s", e)
