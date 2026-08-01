from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import LiveSession, LiveSessionRsvp

from . import router
from ._helpers import _email_attendance_cert, _issue_attendance_cert
from ._schemas import MarkAttendanceIn

logger = logging.getLogger(__name__)


@router.post("/{session_id}/mark-attendance")
def mark_attendance(session_id: int, body: MarkAttendanceIn,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    s = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    marked = 0
    certs_issued = 0
    for uid in body.user_ids:
        rsvp = db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.session_id == session_id,
            LiveSessionRsvp.user_id == uid,
        ).first()
        if not rsvp:
            # Auto-create an RSVP row so walk-ins get tracked
            rsvp = LiveSessionRsvp(session_id=session_id, user_id=uid, status="RSVP")
            db.add(rsvp)
            db.flush()
        rsvp.status = body.status
        rsvp.attendance_marked_at = datetime.now(timezone.utc)
        marked += 1
        # Iter 27 — Auto-issue attendance cert on ATTENDED (idempotent)
        # Iter 28 — Email the certificate link to the learner via outbox
        if body.status == "ATTENDED":
            cert = _issue_attendance_cert(db, uid, s)
            if cert is not None:
                certs_issued += 1
                try:
                    _email_attendance_cert(db, cert, s, current.organization_id)
                except Exception:  # never fail attendance flow on mail issue
                    logger.exception("attendance cert email enqueue failed")
    db.commit()
    return {"marked": marked, "status": body.status,
            "attendance_certs_issued": certs_issued}
