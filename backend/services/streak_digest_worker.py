"""Iter 30 — Streak-leaderboard weekly digest email worker.

Every Monday at 08:00 UTC, emails each organisation's ADMIN role
holders a compact summary of the top 5 streak leaders + their own
learners' streak stats. Reuses the `emails.streak_digest` template
label so it's discoverable in the outbox admin view.

Runs via APScheduler cron. Idempotent — Monday-only + a
`digest_last_sent_at` per-org marker prevents replays if the worker
restarts mid-window.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from core.database import SessionLocal
from models import Organization, User
from services.gamification_service import GamificationService
from services.mail_service import MailService

logger = logging.getLogger(__name__)


def _rank_org_streaks(db, organization_id: int, limit: int = 5):
    """Compute the top-N streak list for an org. Same logic as the
    /streak-leaderboard endpoint but decoupled for reuse."""
    gam = GamificationService(db)
    users = db.query(User).filter(
        User.organization_id == organization_id,
        User.is_active == True,  # noqa: E712
    ).all()
    entries = []
    for u in users:
        try:
            s = gam.compute_learning_streak(u.id)
        except Exception:
            continue
        if s["current_streak"] <= 0 and s["longest_streak"] <= 0:
            continue
        entries.append({
            "user_id": u.id,
            "name": u.name or u.email.split("@")[0],
            "email": u.email,
            "current_streak": s["current_streak"],
            "longest_streak": s["longest_streak"],
        })
    entries.sort(key=lambda e: (
        -e["current_streak"], -e["longest_streak"], e["user_id"],
    ))
    return entries[:limit], len(entries)


def _digest_body(org_name: str, top: list, total: int) -> tuple[str, str]:
    """Return (html, text) email bodies for the leaderboard digest."""
    if not top:
        html = f"<p>No active streaks in <strong>{org_name}</strong> this week — encourage your learners to view a slide daily!</p>"
        text = f"No active streaks in {org_name} this week."
        return html, text
    rows_html = []
    rows_text = []
    for i, e in enumerate(top, start=1):
        rows_html.append(
            f"<tr><td style='padding:6px 12px;'>{i}</td>"
            f"<td style='padding:6px 12px;'><strong>{e['name']}</strong></td>"
            f"<td style='padding:6px 12px; color:#f97316;'>🔥 {e['current_streak']}d</td>"
            f"<td style='padding:6px 12px; color:#94a3b8;'>best {e['longest_streak']}d</td></tr>"
        )
        rows_text.append(f"  {i}. {e['name']} — {e['current_streak']}d (best {e['longest_streak']}d)")
    html = (
        f"<h2 style='margin-top:0'>{org_name} — Top learning streaks this week</h2>"
        f"<p>{total} learners are on active streaks. Here are your leaders:</p>"
        f"<table style='border-collapse:collapse;font-family:system-ui,sans-serif;'>"
        + "".join(rows_html) +
        "</table>"
        f"<p style='margin-top:20px;color:#64748b;font-size:13px;'>Sent by the IFPI Learning weekly digest.</p>"
    )
    text = f"{org_name} — Top learning streaks this week ({total} active):\n" + "\n".join(rows_text)
    return html, text


def run_streak_digest_pass() -> dict:
    """Scan every org, compute the leaderboard, and email each ADMIN
    of that org. Returns stats dict."""
    stats = {"orgs_scanned": 0, "emails_queued": 0, "orgs_skipped": 0}
    db = SessionLocal()
    try:
        orgs = db.query(Organization).all()
        for org in orgs:
            stats["orgs_scanned"] += 1
            try:
                top, total = _rank_org_streaks(db, org.id)
            except Exception:
                stats["orgs_skipped"] += 1
                continue
            if not top:
                continue
            admins = db.query(User).filter(
                User.organization_id == org.id,
                User.is_active == True,  # noqa: E712
                User.streak_digest_enabled == True,  # noqa: E712 — Iter 31 opt-out
            ).all()
            admins = [u for u in admins if any(
                ur.role in {"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"}
                for ur in (u.user_roles or [])
            )]
            if not admins:
                continue
            html, text = _digest_body(org.name, top, total)
            subject = f"🔥 {org.name} — Top learning streaks this week"
            mail = MailService(db)
            for a in admins:
                try:
                    mail.send_email(
                        to_email=a.email, to_name=a.name,
                        subject=subject, body_html=html, body_text=text,
                        template="streak_digest",
                        organization_id=org.id, user_id=a.id,
                    )
                    stats["emails_queued"] += 1
                except Exception:  # pragma: no cover — defensive
                    logger.exception("streak digest email failed for %s", a.email)
        db.commit()
    finally:
        db.close()
    return stats


def _tick() -> None:  # scheduler entrypoint
    try:
        stats = run_streak_digest_pass()
        if stats.get("emails_queued", 0) > 0:
            logger.info("streak-digest: %s", stats)
    except Exception as e:  # pragma: no cover
        logger.exception("streak-digest tick failed: %s", e)
