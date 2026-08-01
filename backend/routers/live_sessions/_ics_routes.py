from __future__ import annotations

import io as _io
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Response
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import LiveSession, LiveSessionRsvp, Organization, User

from . import router
from ._helpers import _ics_escape, _sign_subscription_token, _verify_subscription_token


@router.get("/{session_id}/ics")
def download_ics(session_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(get_current_user)):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    start = s.start_at.astimezone(timezone.utc) if s.start_at.tzinfo else s.start_at.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=s.duration_minutes)
    desc_line = (s.description or "") + "\n\nJoin: " + s.meeting_url
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IFPI Learning//Live Sessions//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:live-session-{s.id}@ifpi.org",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_ics_escape(s.title)}",
        f"DESCRIPTION:{_ics_escape(desc_line)}",
        f"URL:{s.meeting_url}",
        f"LOCATION:{_ics_escape(s.meeting_url)}",
    ]
    if s.recurrence_rule:
        lines.append(f"RRULE:{s.recurrence_rule}")
        cancelled_children = db.query(LiveSession).filter(
            LiveSession.parent_series_id == s.id,
            LiveSession.cancelled_at.isnot(None),
        ).all()
        for child in cancelled_children:
            ex = child.start_at.astimezone(timezone.utc) if child.start_at.tzinfo else child.start_at.replace(tzinfo=timezone.utc)
            lines.append(f"EXDATE:{ex.strftime('%Y%m%dT%H%M%SZ')}")
    if s.cancelled_at:
        lines.append("STATUS:CANCELLED")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    ics = "\r\n".join(lines)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="live-session-{s.id}.ics"'},
    )


@router.post("/subscribe-url")
def create_subscription_url(kind: str = "admin", db: Session = Depends(get_db),
                            current: CurrentUser = Depends(get_current_user)):
    """Return a URL the caller can hand to their calendar app."""
    if kind not in ("admin", "learner", "my_rsvps"):
        raise HTTPException(status_code=400,
                            detail="kind must be 'admin', 'learner' or 'my_rsvps'")
    if kind == "admin":
        if not current.has_any_role({"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"}):
            raise HTTPException(status_code=403, detail="Not authorised for admin subscription")
    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    version = org.subscription_secret_version if org else 1
    token = _sign_subscription_token(current.id, kind, current.organization_id, version)
    return {"token": token, "path": f"/api/live-sessions/subscribe/{token}.ics",
            "secret_version": version}


@router.post("/subscribe-url/rotate")
def rotate_subscription_secret(db: Session = Depends(get_db),
                                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Iter 25 — Bump the org's subscription_secret_version. Every
    outstanding subscription URL for this org immediately 401s."""
    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    old = org.subscription_secret_version or 1
    org.subscription_secret_version = old + 1
    db.commit()
    return {"old_version": old, "new_version": org.subscription_secret_version,
            "rotated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/subscribe/{token}.ics")
def subscribe_ics(token: str, db: Session = Depends(get_db)):
    """Iter 24 — Persistent calendar subscription. Token authenticates
    the request; NO cookie/JWT required."""
    payload = _verify_subscription_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid subscription token")

    user_id = payload["sub"]
    kind = payload["kind"]
    token_sv = payload.get("sv", 1)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    current_sv = org.subscription_secret_version if org else 1
    if current_sv != token_sv:
        raise HTTPException(status_code=401, detail="Subscription URL revoked (secret rotated)")

    now = datetime.now(timezone.utc)
    q = db.query(LiveSession).filter(
        LiveSession.organization_id == user.organization_id,
        LiveSession.start_at >= now - timedelta(days=1),
        LiveSession.cancelled_at.is_(None),
    )
    if kind == "learner":
        all_upcoming = q.order_by(LiveSession.start_at.asc()).all()
        cohort_ok = [s for s in all_upcoming if (not s.cohort) or s.cohort == user.cohort]
        sessions = cohort_ok
    elif kind == "my_rsvps":
        my_rsvp_ids = [r.session_id for r in db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.user_id == user_id,
            LiveSessionRsvp.status == "RSVP",
        ).all()]
        sessions = q.filter(LiveSession.id.in_(my_rsvp_ids)).order_by(
            LiveSession.start_at.asc()
        ).all() if my_rsvp_ids else []
    else:
        sessions = q.order_by(LiveSession.start_at.asc()).all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IFPI Learning//Live Sessions Subscription//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:IFPI Live Sessions ({kind})",
        f"X-WR-CALDESC:Auto-updating subscription for {user.email}",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for s in sessions:
        start = s.start_at.astimezone(timezone.utc) if s.start_at.tzinfo else s.start_at.replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=s.duration_minutes)
        desc = (s.description or "") + "\n\nJoin: " + s.meeting_url
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:live-session-{s.id}@ifpi.org",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{_ics_escape(s.title)}",
            f"DESCRIPTION:{_ics_escape(desc)}",
            f"URL:{s.meeting_url}",
            f"LOCATION:{_ics_escape(s.meeting_url)}",
            "END:VEVENT",
        ])
    lines.extend(["END:VCALENDAR", ""])
    body = "\r\n".join(lines)
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/subscribe-url/qr")
def subscribe_url_qr(
    kind: str = "admin",
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 25 — Return an SVG QR code encoding the current user's
    subscription URL."""
    if kind not in ("admin", "learner", "my_rsvps"):
        raise HTTPException(status_code=400, detail="kind must be 'admin', 'learner' or 'my_rsvps'")
    if kind == "admin" and not current.has_any_role({"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"}):
        raise HTTPException(status_code=403, detail="Not authorised for admin subscription")

    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    version = org.subscription_secret_version if org else 1
    token = _sign_subscription_token(current.id, kind, current.organization_id, version)

    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    url = f"{base}/api/live-sessions/subscribe/{token}.ics" if base else \
          f"/api/live-sessions/subscribe/{token}.ics"

    import qrcode
    import qrcode.image.svg as svg
    qr = qrcode.QRCode(box_size=8, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=svg.SvgPathImage)
    buf = _io.BytesIO()
    img.save(buf)
    svg_bytes = buf.getvalue()
    return Response(
        content=svg_bytes, media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )
