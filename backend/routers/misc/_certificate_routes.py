from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import ADMIN_ROLES
from models import Certificate, User
from schemas import CertificateOut

from . import cert_router
from ._schemas import BulkEmailIn, BulkRevokeIn, BulkUnrevokeIn, BulkZipIn


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

    def _title(c):
        if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id in sessions:
            return sessions[c.live_session_id].title
        return c.course.title if c.course else None

    return [CertificateOut(
        id=c.id, code=c.code, type=c.type,
        course_title=_title(c),
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


@cert_router.post("/bulk-email")
def bulk_email_certificates(
    body: BulkEmailIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 31 — Bulk re-email certificate download links to owners.
    Useful for resending after infra issues or re-notifying learners
    of a re-issued cert. Uses standard outbox pipeline."""
    from models import User as UserModel, LiveSession, Organization
    from services.mail_service import MailService
    mail = MailService(db)
    org = db.query(Organization).filter(
        Organization.id == current.organization_id
    ).first()
    org_name = org.name if org else "IFPI Learning"
    queued = 0
    results = []
    for cid in body.certificate_ids:
        c = db.query(Certificate).filter(Certificate.id == cid).first()
        if not c:
            results.append({"id": cid, "status": "not_found"}); continue
        if c.user and c.user.organization_id != current.organization_id:
            results.append({"id": cid, "status": "forbidden"}); continue
        if c.revoked_at:
            results.append({"id": cid, "status": "revoked_skipped"}); continue
        user = c.user
        if not user or not user.email:
            results.append({"id": cid, "status": "no_email"}); continue
        title = (c.course.title if c.course
                 else (db.query(LiveSession).filter(
                     LiveSession.id == c.live_session_id).first().title
                     if c.live_session_id else "IFPI Certificate"))
        try:
            mail.send_email(
                to_email=user.email, to_name=user.name,
                subject=f"Your certificate for {title}",
                body_html=f'<p>Hi {user.name or "there"},</p>'
                          f'<p>Here is your certificate for <strong>{title}</strong>.'
                          f'</p><p><a href="/api/certificates/{c.id}/pdf">'
                          f'Download PDF</a> · <a href="/verify/{c.code}">'
                          f'Verify link</a></p><p>— {org_name}</p>',
                body_text=f"Hi {user.name or 'there'},\n\n"
                          f"Here is your certificate for {title}.\n"
                          f"Download PDF: /api/certificates/{c.id}/pdf\n"
                          f"Verify: /verify/{c.code}\n\n— {org_name}",
                template="cert_resend",
                organization_id=current.organization_id, user_id=user.id,
            )
            queued += 1
            results.append({"id": cid, "status": "queued"})
        except Exception:  # pragma: no cover
            results.append({"id": cid, "status": "send_failed"})
    db.commit()
    return {"queued_count": queued, "results": results}


@cert_router.post("/bulk-zip")
def bulk_zip_certificates(
    body: BulkZipIn,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 31 — Bundle up to 100 cert PDFs into a single ZIP for
    admin download. Skips revoked + cross-tenant certs silently. Caps
    at 100 to prevent runaway memory usage."""
    import io, zipfile
    from models import Organization, LiveSession
    from services.pdf_certificate_service import render_certificate
    if len(body.certificate_ids) > 100:
        raise HTTPException(status_code=400, detail="Max 100 certs per bulk zip")
    base = str(request.base_url).rstrip("/")
    buf = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in body.certificate_ids:
            c = db.query(Certificate).filter(Certificate.id == cid).first()
            if not c or c.revoked_at:
                continue
            if c.user and c.user.organization_id != current.organization_id:
                continue
            org = db.query(Organization).filter(
                Organization.id == c.user.organization_id).first() if c.user else None
            if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
                sess = db.query(LiveSession).filter(
                    LiveSession.id == c.live_session_id).first()
                title = sess.title if sess else "Live Session"
                cert_type = "Live Session Attendance"
            else:
                title = c.course.title if c.course else "IFPI Course"
                cert_type = "Course Completion" if c.type == "COURSE_COMPLETION" \
                    else c.type.replace("_", " ").title()
            try:
                pdf = render_certificate(
                    recipient_name=c.user.name or c.user.email,
                    course_title=title,
                    certificate_code=c.code,
                    issued_at=c.issued_at,
                    verify_url=f"{base}/verify/{c.code}",
                    score=c.score,
                    cert_type=cert_type,
                    organisation_name=org.name if org else "IFPI Learning",
                    organisation_logo_url=org.logo_url if org else None,
                    accent_color=(org.cert_accent_color or org.primary_color or "#6366f1")
                                 if org else "#6366f1",
                    signature_text=org.cert_signature_text if org else None,
                    signature_image_url=org.cert_signature_image_url if org else None,
                    footer_text=org.cert_footer_text if org else None,
                )
                safe_name = (c.user.name or c.user.email or f"cert-{c.id}").replace("/", "_")
                zf.writestr(f"{safe_name}-{c.code[:8]}.pdf", pdf)
                added += 1
            except Exception:
                continue
    if added == 0:
        raise HTTPException(status_code=400, detail="No certs to bundle")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="certificates-{added}.zip"',
            "X-Certs-Bundled": str(added),
        },
    )


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
    def _title(c):
        if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id in sessions:
            return sessions[c.live_session_id].title
        return c.course.title if c.course else None
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [{
            "id": c.id, "code": c.code, "type": c.type,
            "title": _title(c),
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


@cert_router.get("/verify/{code}")
def verify_certificate(code: str, db: Session = Depends(get_db)):
    from models import LiveSession
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    # Iter 27 — attendance certs surface the session title
    title = c.course.title if c.course else None
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        if sess:
            title = sess.title
    return {
        "valid": not bool(c.revoked_at),
        "code": c.code, "type": c.type,
        "recipient_name": c.user.name if c.user else None,
        "course_title": title,
        "issued_at": c.issued_at,
        # Iter 29 — revocation state (nulls when not revoked)
        "revoked_at": c.revoked_at,
        "revoked_reason": c.revoked_reason,
    }


@cert_router.get("/verify/{code}/og-image.svg", response_class=Response)
def certificate_og_image(code: str, db: Session = Depends(get_db)):
    """Iter 28 — SVG OG image for social share previews. 1200×630 to
    match Twitter/LinkedIn card ratios. Lightweight, static, safe to
    inline in HTML meta tags."""
    from models import LiveSession, Organization
    from xml.sax.saxutils import escape
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = f"Attended · {sess.title}" if sess else "Live Session Attendance"
    else:
        title = c.course.title if c.course else "IFPI Certificate"

    recipient = (c.user.name if c.user and c.user.name else "A learner")
    org_name = "IFPI Learning"
    if c.user and c.user.organization_id:
        org = db.query(Organization).filter(Organization.id == c.user.organization_id).first()
        if org:
            org_name = org.name

    # Truncate to avoid overflow
    def _fit(s: str, n: int) -> str:
        return s if len(s) <= n else s[:n - 1].rstrip() + "…"
    t = escape(_fit(title, 60))
    r = escape(_fit(recipient, 40))
    o = escape(_fit(org_name, 40))

    # Iter 29 — Revoked overlay
    revoked_overlay = ""
    if c.revoked_at:
        revoked_overlay = """
  <g opacity="0.92">
    <rect x="0" y="200" width="1200" height="120" fill="#dc2626" />
    <text x="600" y="278" text-anchor="middle"
          font-family="system-ui, -apple-system, Segoe UI, sans-serif"
          font-size="72" font-weight="800" fill="white"
          letter-spacing="8">REVOKED</text>
  </g>"""

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#eef2ff" />
      <stop offset="100%" stop-color="#ede9fe" />
    </linearGradient>
    <linearGradient id="ribbon" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1" />
      <stop offset="100%" stop-color="#8b5cf6" />
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)" />
  <rect x="60" y="80" width="1080" height="470" rx="24" fill="white" opacity="0.95" />
  <rect x="60" y="80" width="1080" height="8" fill="url(#ribbon)" />
  <text x="600" y="200" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="28" fill="#6366f1" font-weight="600">CERTIFICATE OF ACHIEVEMENT</text>
  <text x="600" y="290" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="52" fill="#1e293b" font-weight="700">{r}</text>
  <text x="600" y="360" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="22" fill="#64748b">has successfully completed</text>
  <text x="600" y="420" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="34" fill="#4338ca" font-weight="600">{t}</text>
  <text x="600" y="490" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="18" fill="#94a3b8">Awarded by {o}</text>
  <text x="600" y="530" text-anchor="middle" font-family="ui-monospace, monospace"
        font-size="14" fill="#cbd5e1">verify: {escape(code)}</text>
{revoked_overlay}
</svg>"""
    return Response(svg, media_type="image/svg+xml", headers={
        # Iter 29 — revoked certs: shorter cache so LinkedIn re-fetches
        # sooner and reflects the revocation state in previews.
        "Cache-Control": "public, max-age=300" if c.revoked_at
                         else "public, max-age=86400",
    })


@cert_router.get("/{cert_id}/pdf")
def download_certificate_pdf(
    cert_id: int, request: Request, db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Generate a branded PDF for a certificate. Owner or admin only.

    Iter 27 — Attendance certs (type=LIVE_SESSION_ATTENDANCE) render
    the session title as the "course" line and use "Live Session
    Attendance" as the cert type label."""
    from models import Organization, LiveSession
    from services.pdf_certificate_service import render_certificate
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user_id != current.id and not current.has_any_role({"ADMIN", "SUPER_ADMIN"}):
        raise HTTPException(status_code=403, detail="Forbidden")
    # Iter 29 — Revoked certs cannot be re-downloaded (410 Gone)
    # unless the caller is admin (admins may need to inspect the
    # original for audit).
    if c.revoked_at and not current.has_any_role({"ADMIN", "SUPER_ADMIN"}):
        raise HTTPException(status_code=410, detail="Certificate has been revoked")
    base = str(request.base_url).rstrip("/")
    verify_url = f"{base}/verify/{c.code}"
    org = db.query(Organization).filter(Organization.id == c.user.organization_id).first() if c.user else None

    # Resolve title + cert type label
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = sess.title if sess else "Live Session"
        cert_type = "Live Session Attendance"
    else:
        title = c.course.title if c.course else "IFPI Course"
        cert_type = "Course Completion" if c.type == "COURSE_COMPLETION" else c.type.replace("_", " ").title()

    # Iter 38 Phase C — wrap PDF render in a circuit breaker. If the
    # renderer wedges (memory pressure, font stall, playwright crash),
    # after 5 consecutive failures we OPEN the breaker for 30s and
    # return `503 Service Unavailable + Retry-After` to the learner
    # instead of a hard 500. Learning flow (enrollment, progress,
    # quizzes) stays live regardless.
    from services.circuit_breaker import cert_generation_breaker, CircuitBreakerOpen
    breaker = cert_generation_breaker()
    try:
        pdf = breaker.call(
            render_certificate,
            recipient_name=c.user.name or c.user.email,
            course_title=title,
            certificate_code=c.code,
            issued_at=c.issued_at,
            verify_url=verify_url,
            score=c.score,
            cert_type=cert_type,
            organisation_name=org.name if org else "IFPI Learning",
            organisation_logo_url=org.logo_url if org else None,
            accent_color=(org.cert_accent_color or org.primary_color or "#6366f1") if org else "#6366f1",
            signature_text=org.cert_signature_text if org else None,
            signature_image_url=org.cert_signature_image_url if org else None,
            footer_text=org.cert_footer_text if org else None,
        )
    except CircuitBreakerOpen:
        raise HTTPException(
            status_code=503,
            detail="Certificate PDF renderer is temporarily unavailable. "
                   "Your certificate is safe — please try again in 30 seconds.",
            headers={"Retry-After": "30"},
        )
    filename = f"IFPI-Certificate-{c.code}.pdf"
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
