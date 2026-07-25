from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from models import Certificate, LiveSession, LiveSessionRsvp, Organization, User

logger = logging.getLogger(__name__)

# ── Recurrence helper ────────────────────────────────────────────────
_MAX_RECURRENCE_INSTANCES = 26


def _expand_recurrence(rrule_str: str, dtstart: datetime) -> list[datetime]:
    """Return a list of concrete `datetime`s for the recurrence,
    excluding the seed dtstart (which is the head). Empty on parse error
    to keep failures graceful — the head instance is still created.

    Note: python-dateutil's `rrulestr` truncates microseconds on emitted
    occurrences, so we compare on second-resolution to detect the
    dtstart's "twin" and skip it — otherwise the head would be
    duplicated as a child."""
    from dateutil.rrule import rrulestr

    try:
        rule = rrulestr(rrule_str, dtstart=dtstart)
    except Exception:
        return []
    seed_seconds = dtstart.replace(microsecond=0)
    out: list[datetime] = []
    for occurrence in rule:
        # Skip the head's twin (first occurrence when the RRULE includes dtstart)
        if occurrence.replace(microsecond=0) == seed_seconds and not out:
            continue
        out.append(occurrence)
        if len(out) >= _MAX_RECURRENCE_INSTANCES:
            break
    return out


def _serialize(s: LiveSession, include_rsvps: bool = False) -> dict:
    out = {
        "id": s.id,
        "title": s.title,
        "description": s.description,
        "meeting_url": s.meeting_url,
        "start_at": s.start_at.isoformat() if s.start_at else None,
        "duration_minutes": s.duration_minutes,
        "host_name": s.host_name,
        "cohort": s.cohort,
        "course_id": s.course_id,
        "max_attendees": s.max_attendees,
        "recurrence_rule": s.recurrence_rule,
        "parent_series_id": s.parent_series_id,
        "reminder_sent_at": s.reminder_sent_at.isoformat() if s.reminder_sent_at else None,
        "cancelled_at": s.cancelled_at.isoformat() if s.cancelled_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "rsvp_count": len([r for r in s.rsvps if r.status != "CANCELLED"]),
        "attendance_count": len([r for r in s.rsvps if r.status == "ATTENDED"]),
    }
    if include_rsvps:
        out["rsvps"] = [{
            "user_id": r.user_id,
            "status": r.status,
            "rsvped_at": r.rsvped_at.isoformat() if r.rsvped_at else None,
            "attendance_marked_at": r.attendance_marked_at.isoformat() if r.attendance_marked_at else None,
        } for r in s.rsvps]
    return out


def _issue_attendance_cert(db: Session, user_id: int, session: LiveSession):
    """Iter 27 — Idempotent attendance-certificate issuance. Skips if
    the user already has a cert for this session. Returns the new
    Certificate row or None."""
    existing = db.query(Certificate).filter(
        Certificate.user_id == user_id,
        Certificate.live_session_id == session.id,
        Certificate.type == "LIVE_SESSION_ATTENDANCE",
    ).first()
    if existing:
        return None
    cert = Certificate(
        user_id=user_id,
        live_session_id=session.id,
        course_id=session.course_id,
        type="LIVE_SESSION_ATTENDANCE",
    )
    db.add(cert)
    db.flush()
    return cert


def _email_attendance_cert(db: Session, cert, session: LiveSession,
                           organization_id: int) -> None:
    """Iter 28 — Queue an outbox email containing the branded cert PDF.

    Uses the standard MailService (which queues to `outbox_messages`
    and lets the outbox worker deliver via per-tenant SMTP or system
    relay). PDF is regenerated on demand by the worker via the
    attachment URL — we only enqueue a link, not the bytes, keeping
    the outbox row small."""
    from services.mail_service import MailService

    user = db.query(User).filter(User.id == cert.user_id).first()
    if not user or not user.email:
        return
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    org_name = org.name if org else "IFPI Learning"
    cert_link = f"/verify/{cert.code}"
    pdf_link = f"/api/certificates/{cert.id}/pdf"

    subject = f"Your attendance certificate for {session.title}"
    body_html = f"""
    <p>Hi {user.name or 'there'},</p>
    <p>Thanks for attending <strong>{session.title}</strong>. Your
    certificate of attendance is ready.</p>
    <p><a href="{pdf_link}" style="background:#4f46e5;color:white;
        padding:10px 16px;text-decoration:none;border-radius:6px;
        display:inline-block;">Download certificate (PDF)</a></p>
    <p>Prefer to verify it later? Share this link:
    <br/><code>{cert_link}</code></p>
    <p>— {org_name}</p>
    """
    body_text = (
        f"Hi {user.name or 'there'},\n\n"
        f"Thanks for attending {session.title}. Your certificate of "
        f"attendance is ready.\n\n"
        f"Download PDF: {pdf_link}\n"
        f"Verify: {cert_link}\n\n"
        f"— {org_name}"
    )
    MailService(db).send_email(
        to_email=user.email, to_name=user.name,
        subject=subject, body_html=body_html, body_text=body_text,
        template="live_session_attendance",
        organization_id=organization_id, user_id=user.id,
    )


# ── ICS helpers ──────────────────────────────────────────────────────
def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


# ── Subscription token helpers ───────────────────────────────────────
def _sub_secret() -> bytes:
    """Signing key for subscription tokens. Uses JWT_SECRET so
    ops don't need to configure yet another secret."""
    return (os.environ.get("JWT_SECRET") or "dev-only-secret").encode()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign_subscription_token(user_id: int, kind: str, org_id: int, version: int) -> str:
    """Payload includes `sv` (secret version scoped to the org). Bumping
    the org's `subscription_secret_version` column invalidates every
    token issued at the old version — the calendar URL 404s but the
    user's login session is untouched."""
    payload = json.dumps({
        "sub": user_id, "kind": kind, "org": org_id, "sv": version,
    }, sort_keys=True).encode()
    sig = hmac.new(_sub_secret(), payload, hashlib.sha256).digest()
    return f"{_b64url(payload)}.{_b64url(sig)}"


def _verify_subscription_token(token: str) -> dict | None:
    try:
        payload_b64, sig_b64 = token.split(".")
        payload = _b64url_decode(payload_b64)
        expected_sig = hmac.new(_sub_secret(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
            return None
        return json.loads(payload)
    except Exception:
        return None
