from __future__ import annotations

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import Certificate

from . import cert_router
from ._cert_helpers import resolve_certificate_title


@cert_router.get("/admin-list")
def admin_list_certificates(
    q: str | None = None,
    type: str | None = None,
    status: str | None = None,  # "all" | "active" | "revoked"
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 30 — Admin view: paginated list of ALL certs in the org.
    Supports search by learner name/email/code, filter by type, and
    revocation status. Backs the bulk-ops table."""
    from models import User as UserModel, LiveSession
    query = db.query(Certificate).join(
        UserModel, UserModel.id == Certificate.user_id
    ).filter(UserModel.organization_id == current.organization_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (UserModel.name.ilike(like)) | (UserModel.email.ilike(like)) |
            (Certificate.code.ilike(like))
        )
    if type:
        query = query.filter(Certificate.type == type)
    if status == "revoked":
        query = query.filter(Certificate.revoked_at.isnot(None))
    elif status == "active":
        query = query.filter(Certificate.revoked_at.is_(None))
    total = query.count()
    rows = (query.order_by(Certificate.issued_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    session_ids = [c.live_session_id for c in rows if c.live_session_id]
    sessions = {s.id: s for s in db.query(LiveSession).filter(
        LiveSession.id.in_(session_ids))} if session_ids else {}
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [{
            "id": c.id, "code": c.code, "type": c.type,
            "title": resolve_certificate_title(c, sessions),
            "recipient_name": c.user.name if c.user else None,
            "recipient_email": c.user.email if c.user else None,
            "issued_at": c.issued_at,
            "revoked_at": c.revoked_at,
            "revoked_reason": c.revoked_reason,
            "score": c.score,
        } for c in rows],
    }


@cert_router.get("/admin-export.csv")
def admin_export_certificates_csv(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 30 — CSV export for compliance / auditors. All org certs
    with status + revocation metadata."""
    import csv, io
    from models import User as UserModel, LiveSession
    rows = db.query(Certificate).join(
        UserModel, UserModel.id == Certificate.user_id
    ).filter(UserModel.organization_id == current.organization_id
    ).order_by(Certificate.issued_at.desc()).all()
    session_ids = [c.live_session_id for c in rows if c.live_session_id]
    sessions = {s.id: s for s in db.query(LiveSession).filter(
        LiveSession.id.in_(session_ids))} if session_ids else {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "id", "code", "type", "title", "recipient_name", "recipient_email",
        "issued_at", "score", "status", "revoked_at", "revoked_reason",
    ])
    for c in rows:
        title = (sessions[c.live_session_id].title
                 if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id in sessions
                 else (c.course.title if c.course else ""))
        w.writerow([
            c.id, c.code, c.type, title,
            c.user.name if c.user else "",
            c.user.email if c.user else "",
            c.issued_at.isoformat() if c.issued_at else "",
            c.score if c.score is not None else "",
            "REVOKED" if c.revoked_at else "ACTIVE",
            c.revoked_at.isoformat() if c.revoked_at else "",
            c.revoked_reason or "",
        ])
    return Response(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="certificates.csv"'},
    )
