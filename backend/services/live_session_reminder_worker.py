"""Iter 23 — Live Session reminder worker.

Called every minute from the outbox scheduler (see `outbox_worker.py`).
For each session starting in [now+14min, now+16min] with `reminder_sent_at
IS NULL`, we queue a reminder email to every ACTIVE RSVP (status='RSVP',
never CANCELLED) and stamp `reminder_sent_at` so we never spam twice.

The 2-minute window (14–16 min) absorbs the scheduler's 60s tick jitter
without duplicate sends. If a session's reminder window is missed (e.g.
worker was down), we intentionally do NOT back-fill — the email would
arrive after the session started and be worse than useless.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import LiveSession, LiveSessionRsvp, User
from services.mail_service import MailService

logger = logging.getLogger(__name__)


REMINDER_WINDOW_MIN_MINUTES = 14
REMINDER_WINDOW_MAX_MINUTES = 16


def _render_reminder(session: LiveSession, user: User) -> tuple[str, str, str]:
    """Return (subject, html, text) for the reminder email."""
    start_local = session.start_at.strftime("%Y-%m-%d %H:%M UTC")
    subject = f"Reminder: '{session.title}' starts in 15 minutes"
    text = (
        f"Hi {user.name or user.email},\n\n"
        f"Your live session '{session.title}' starts at {start_local} "
        f"(in ~15 minutes).\n\n"
        f"Join here: {session.meeting_url}\n\n"
        + (f"Hosted by: {session.host_name}\n" if session.host_name else "")
        + "\nSee you there!\nIFPI Learning"
    )
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:24px;">
      <h2 style="color:#4f46e5;margin:0 0 12px;">Starting in 15 minutes</h2>
      <p style="color:#0f172a;font-size:16px;line-height:1.5;">
        Hi {user.name or user.email}, your live session is about to start:
      </p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:16px 0;">
        <p style="font-weight:600;font-size:18px;color:#0f172a;margin:0 0 6px;">{session.title}</p>
        <p style="color:#64748b;font-size:13px;margin:0 0 12px;">{start_local}
          {" · Hosted by " + session.host_name if session.host_name else ""}
        </p>
        <a href="{session.meeting_url}" style="display:inline-block;background:#4f46e5;color:white;
          padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;">
          Join now →
        </a>
      </div>
      <p style="color:#94a3b8;font-size:12px;margin-top:24px;">IFPI Learning · Live Sessions</p>
    </div>
    """
    return subject, html, text


def tick(db: Session) -> int:
    """Send 15-min reminder emails for sessions in the window. Returns
    the number of reminder-batches sent (one per session, not per RSVP)."""
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(minutes=REMINDER_WINDOW_MIN_MINUTES)
    window_end = now + timedelta(minutes=REMINDER_WINDOW_MAX_MINUTES)

    sessions = (
        db.query(LiveSession)
        .filter(LiveSession.reminder_sent_at.is_(None))
        .filter(LiveSession.start_at >= window_start)
        .filter(LiveSession.start_at <= window_end)
        .filter(LiveSession.cancelled_at.is_(None))  # Iter 24 — never remind about cancelled sessions
        .all()
    )
    if not sessions:
        return 0

    mailer = MailService(db)
    sent_batches = 0
    for s in sessions:
        # Find all active RSVPs (RSVP status, not CANCELLED)
        rsvps = (
            db.query(LiveSessionRsvp, User)
            .join(User, User.id == LiveSessionRsvp.user_id)
            .filter(LiveSessionRsvp.session_id == s.id)
            .filter(LiveSessionRsvp.status == "RSVP")
            .filter(User.is_active.is_(True))
            .all()
        )
        for _, user in rsvps:
            if not user.email:
                continue
            subject, html, text = _render_reminder(s, user)
            mailer.send_email(
                to_email=user.email, to_name=user.name, subject=subject,
                body_html=html, body_text=text,
                template="live_session_reminder",
                organization_id=s.organization_id, user_id=user.id,
            )
        # Stamp the reminder even if no RSVPs — otherwise we'd re-check every minute
        s.reminder_sent_at = now
        sent_batches += 1
    db.commit()
    logger.info("Live-session reminder tick: %d session(s) processed", sent_batches)
    return sent_batches
