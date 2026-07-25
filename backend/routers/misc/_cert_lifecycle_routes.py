from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import ADMIN_ROLES
from models import Certificate, User
from schemas import CertificateOut

from . import cert_router
from ._cert_helpers import resolve_certificate_title
from ._schemas import BulkRevokeIn, BulkUnrevokeIn


@cert_router.get("", response_model=list[CertificateOut])
def my_certificates(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    if current.has_any_role(ADMIN_ROLES):
        rows = db.query(Certificate).join(User).filter(
            User.organization_id == current.organization_id,
        ).order_by(Certificate.issued_at.desc()).all()
    else:
        rows = db.query(Certificate).filter(
            Certificate.user_id == current.id,
        ).order_by(Certificate.issued_at.desc()).all()
    # Iter 27 — For attendance certs (LIVE_SESSION_ATTENDANCE), fold
    # the session title into course_title so learner UIs show a
    # meaningful label without a schema change.
    from models import LiveSession
    session_ids = [c.live_session_id for c in rows if c.live_session_id]
    sessions = ({s.id: s for s in db.query(LiveSession).filter(
        LiveSession.id.in_(session_ids)).all()} if session_ids else {})

    return [CertificateOut(
        id=c.id, code=c.code, type=c.type,
        course_title=resolve_certificate_title(c, sessions),
        issued_at=c.issued_at, score=c.score,
        revoked_at=c.revoked_at, revoked_reason=c.revoked_reason,
    ) for c in rows]


@cert_router.post("/{cert_id}/revoke")
def revoke_certificate(
    cert_id: int,
    body: dict | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 29 — Revoke a certificate. Requires ADMIN role. Idempotent
    (re-revoke updates reason but doesn't error). Setting `revoked_at`
    flips the public verify/share pages to a "REVOKED" state so
    LinkedIn/Twitter/etc. refresh their link previews to show
    invalidation.

    Body: {"reason": "..."} — optional. Kept concise (<=255 chars)."""
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user and c.user.organization_id != current.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    reason = None
    if body and isinstance(body.get("reason"), str):
        reason = body["reason"][:255]
    from datetime import datetime as _dt, timezone as _tz
    from models import CertificateRevocationEvent
    from services.webhook_service import emit_safely
    was_already_revoked = c.revoked_at is not None
    c.revoked_at = _dt.now(_tz.utc)
    c.revoked_reason = reason
    db.add(CertificateRevocationEvent(
        certificate_id=c.id,
        actor_user_id=current.id,
        action="REVOKE",
        reason=reason,
    ))
    db.commit()
    # Iter 30 — Fire outgoing webhook so HR / LinkedIn integrations can
    # sync. Only emit if this is a NEW revocation (not a reason-update
    # re-revoke) to keep the event stream idempotent.
    if not was_already_revoked:
        emit_safely(db, current.organization_id, "certificate.revoked", {
            "certificate_id": c.id,
            "code": c.code,
            "user_id": c.user_id,
            "type": c.type,
            "reason": reason,
            "revoked_at": c.revoked_at.isoformat(),
            "actor_user_id": current.id,
        })
    return {"revoked": True, "code": c.code, "revoked_at": c.revoked_at,
            "reason": reason}


@cert_router.post("/{cert_id}/unrevoke")
def unrevoke_certificate(
    cert_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 29 — Clear a revocation flag. In case of a mistaken
    revoke — same tenant check applies."""
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user and c.user.organization_id != current.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    from models import CertificateRevocationEvent
    from services.webhook_service import emit_safely
    was_revoked = c.revoked_at is not None
    c.revoked_at = None
    c.revoked_reason = None
    if was_revoked:
        db.add(CertificateRevocationEvent(
            certificate_id=c.id,
            actor_user_id=current.id,
            action="UNREVOKE",
            reason=None,
        ))
    db.commit()
    if was_revoked:
        emit_safely(db, current.organization_id, "certificate.unrevoked", {
            "certificate_id": c.id,
            "code": c.code,
            "user_id": c.user_id,
            "type": c.type,
            "actor_user_id": current.id,
        })
    return {"revoked": False, "code": c.code}


@cert_router.get("/{cert_id}/revocation-history")
def cert_revocation_history(
    cert_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 30 — Compliance audit trail. Lists REVOKE/UNREVOKE events
    for a cert in reverse-chronological order."""
    from models import CertificateRevocationEvent, User as UserModel
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user and c.user.organization_id != current.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.query(CertificateRevocationEvent).filter(
        CertificateRevocationEvent.certificate_id == cert_id,
    ).order_by(CertificateRevocationEvent.occurred_at.desc()).all()
    # Hydrate actor names
    actor_ids = list({r.actor_user_id for r in rows})
    actors = {u.id: u for u in db.query(UserModel).filter(
        UserModel.id.in_(actor_ids)
    ).all()} if actor_ids else {}
    return [{
        "id": r.id,
        "action": r.action,
        "reason": r.reason,
        "occurred_at": r.occurred_at,
        "actor_user_id": r.actor_user_id,
        "actor_name": actors[r.actor_user_id].name if r.actor_user_id in actors else None,
        "actor_email": actors[r.actor_user_id].email if r.actor_user_id in actors else None,
    } for r in rows]


@cert_router.post("/bulk-revoke")
def bulk_revoke_certificates(
    body: BulkRevokeIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 30 — Bulk revoke. Skips already-revoked certs (idempotent)
    and cross-tenant certs (safety). Returns per-id status list."""
    from datetime import datetime as _dt, timezone as _tz
    from models import CertificateRevocationEvent
    from services.webhook_service import emit_safely
    now = _dt.now(_tz.utc)
    reason = body.reason[:255] if body.reason else None
    results = []
    to_emit = []
    for cid in body.certificate_ids:
        c = db.query(Certificate).filter(Certificate.id == cid).first()
        if not c:
            results.append({"id": cid, "status": "not_found"}); continue
        if c.user and c.user.organization_id != current.organization_id:
            results.append({"id": cid, "status": "forbidden"}); continue
        if c.revoked_at:
            results.append({"id": cid, "status": "already_revoked"}); continue
        c.revoked_at = now
        c.revoked_reason = reason
        db.add(CertificateRevocationEvent(
            certificate_id=c.id, actor_user_id=current.id,
            action="REVOKE", reason=reason,
        ))
        to_emit.append(c)
        results.append({"id": cid, "status": "revoked"})
    db.commit()
    for c in to_emit:
        emit_safely(db, current.organization_id, "certificate.revoked", {
            "certificate_id": c.id, "code": c.code, "user_id": c.user_id,
            "type": c.type, "reason": reason, "revoked_at": c.revoked_at.isoformat(),
            "actor_user_id": current.id, "bulk": True,
        })
    return {
        "revoked_count": sum(1 for r in results if r["status"] == "revoked"),
        "skipped_count": sum(1 for r in results if r["status"] != "revoked"),
        "results": results,
    }


@cert_router.post("/bulk-unrevoke")
def bulk_unrevoke_certificates(
    body: BulkUnrevokeIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 31 — Bulk lift-revocation. Skips currently-active certs
    (idempotent) and cross-tenant certs. Emits `certificate.unrevoked`
    webhook per newly-restored cert."""
    from models import CertificateRevocationEvent
    from services.webhook_service import emit_safely
    to_emit = []
    results = []
    for cid in body.certificate_ids:
        c = db.query(Certificate).filter(Certificate.id == cid).first()
        if not c:
            results.append({"id": cid, "status": "not_found"}); continue
        if c.user and c.user.organization_id != current.organization_id:
            results.append({"id": cid, "status": "forbidden"}); continue
        if not c.revoked_at:
            results.append({"id": cid, "status": "already_active"}); continue
        c.revoked_at = None
        c.revoked_reason = None
        db.add(CertificateRevocationEvent(
            certificate_id=c.id, actor_user_id=current.id,
            action="UNREVOKE", reason=None,
        ))
        to_emit.append(c)
        results.append({"id": cid, "status": "unrevoked"})
    db.commit()
    for c in to_emit:
        emit_safely(db, current.organization_id, "certificate.unrevoked", {
            "certificate_id": c.id, "code": c.code, "user_id": c.user_id,
            "type": c.type, "actor_user_id": current.id, "bulk": True,
        })
    return {
        "unrevoked_count": sum(1 for r in results if r["status"] == "unrevoked"),
        "skipped_count": sum(1 for r in results if r["status"] != "unrevoked"),
        "results": results,
    }
