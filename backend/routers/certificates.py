"""Certificate issuing, verification, PDF, bulk routes, preview + transcript."""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.config import settings
from core.database import get_db
from core.role_registry import ADMIN_ROLES
from models import (
    Certificate, Enrollment, EnrollmentStatus, Exam, ExamAttempt, Organization, User,
)
from schemas import (
    CertificateOut,
)

logger = logging.getLogger(__name__)


# ── Preview (migrated from iter5.py) ─────────────────────────────────
preview_router = APIRouter(prefix="/api/admin/cert-preview", tags=["Cert preview"])


class CertPreviewBody(BaseModel):
    organisation_name: Optional[str] = "Sample Academy"
    organisation_logo_url: Optional[str] = None
    accent_color: Optional[str] = "#6366f1"
    signature_text: Optional[str] = None
    signature_image_url: Optional[str] = None
    footer_text: Optional[str] = None


@preview_router.post("")
def preview_cert(
    body: CertPreviewBody,
    request: Request,
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Render a SAMPLE certificate PDF using the supplied branding — no DB writes.
    Used by the Settings page Live Preview."""
    from services.pdf_certificate_service import render_certificate
    base = settings.public_base_url or str(request.base_url).rstrip("/")
    pdf = render_certificate(
        recipient_name="Jane Sample",
        course_title="Sample Course Title",
        certificate_code="PREVIEW-XXXXX",
        issued_at=datetime.now(timezone.utc),
        verify_url=f"{base}/verify/PREVIEW-XXXXX",
        organisation_name=body.organisation_name or "Sample Academy",
        organisation_logo_url=body.organisation_logo_url,
        accent_color=body.accent_color or "#6366f1",
        signature_text=body.signature_text,
        signature_image_url=body.signature_image_url,
        footer_text=body.footer_text,
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Cache-Control": "no-store"},
    )


# ── Certificates ─────────────────────────────────────────────────────
cert_router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


@cert_router.get("", response_model=List[CertificateOut])
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
    from models import LiveSession, LearningPath
    session_ids = [c.live_session_id for c in rows if c.live_session_id]
    sessions = ({s.id: s for s in db.query(LiveSession).filter(
        LiveSession.id.in_(session_ids)).all()} if session_ids else {})
    path_ids = [c.learning_path_id for c in rows if c.learning_path_id]
    qual_paths = ({p.id: p for p in db.query(LearningPath).filter(
        LearningPath.id.in_(path_ids)).all()} if path_ids else {})

    def _title(c):
        if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id in sessions:
            return sessions[c.live_session_id].title
        if c.type == "QUALIFICATION" and c.learning_path_id in qual_paths:
            from services.pathway_service import _meta
            p = qual_paths[c.learning_path_id]
            return _meta(p).get("designation") or p.title
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
    from models import CertificateRevocationEvent, User as UserModel
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user and c.user.organization_id != current.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.query(CertificateRevocationEvent).filter(
        CertificateRevocationEvent.certificate_id == cert_id,
    ).order_by(CertificateRevocationEvent.occurred_at.desc()).all()
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


class BulkRevokeIn(BaseModel):
    certificate_ids: list[int]
    reason: str | None = None


@cert_router.post("/bulk-revoke")
def bulk_revoke_certificates(
    body: BulkRevokeIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
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


class BulkUnrevokeIn(BaseModel):
    certificate_ids: list[int]


@cert_router.post("/bulk-unrevoke")
def bulk_unrevoke_certificates(
    body: BulkUnrevokeIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
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


class BulkEmailIn(BaseModel):
    certificate_ids: list[int]


@cert_router.post("/bulk-email")
def bulk_email_certificates(
    body: BulkEmailIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    from models import LiveSession, Organization
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
        if c.course:
            title = c.course.title
        elif c.live_session_id:
            ls = db.query(LiveSession).filter(
                LiveSession.id == c.live_session_id).first()
            title = ls.title if ls else "IFPI Certificate"
        else:
            title = "IFPI Certificate"
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


class BulkZipIn(BaseModel):
    certificate_ids: list[int]


@cert_router.post("/bulk-zip")
def bulk_zip_certificates(
    body: BulkZipIn,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    import zipfile
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
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
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
    from models import LearningPath
    path_ids = [c.learning_path_id for c in rows if c.learning_path_id]
    qual_paths = ({p.id: p for p in db.query(LearningPath).filter(
        LearningPath.id.in_(path_ids)).all()} if path_ids else {})
    def _title(c):
        if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id in sessions:
            return sessions[c.live_session_id].title
        if c.type == "QUALIFICATION" and c.learning_path_id in qual_paths:
            from services.pathway_service import _meta
            p = qual_paths[c.learning_path_id]
            return _meta(p).get("designation") or p.title
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
    import csv
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
    title = c.course.title if c.course else None
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        if sess:
            title = sess.title
    elif c.type == "QUALIFICATION" and c.learning_path_id:
        from models import LearningPath
        from services.pathway_service import _meta
        p = db.query(LearningPath).filter(
            LearningPath.id == c.learning_path_id).first()
        if p:
            title = _meta(p).get("designation") or p.title
    return {
        "valid": not bool(c.revoked_at),
        "code": c.code, "type": c.type,
        "recipient_name": c.user.name if c.user else None,
        "course_title": title,
        "issued_at": c.issued_at,
        "revoked_at": c.revoked_at,
        "revoked_reason": c.revoked_reason,
    }


@cert_router.get("/verify/{code}/og-image.svg", response_class=Response)
def certificate_og_image(code: str, db: Session = Depends(get_db)):
    from models import LiveSession, Organization
    from xml.sax.saxutils import escape
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = f"Attended · {sess.title}" if sess else "Live Session Attendance"
    elif c.type == "QUALIFICATION" and c.learning_path_id:
        from models import LearningPath
        from services.pathway_service import _meta
        _p = db.query(LearningPath).filter(
            LearningPath.id == c.learning_path_id).first()
        title = (_meta(_p).get("designation") or _p.title) if _p else "IFPI Qualification"
    else:
        title = c.course.title if c.course else "IFPI Certificate"

    recipient = (c.user.name if c.user and c.user.name else "A learner")
    org_name = "IFPI Learning"
    if c.user and c.user.organization_id:
        org = db.query(Organization).filter(Organization.id == c.user.organization_id).first()
        if org:
            org_name = org.name

    def _fit(s: str, n: int) -> str:
        return s if len(s) <= n else s[:n - 1].rstrip() + "…"
    t = escape(_fit(title, 60))
    r = escape(_fit(recipient, 40))
    o = escape(_fit(org_name, 40))

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
        "Cache-Control": "public, max-age=300" if c.revoked_at
                         else "public, max-age=86400",
    })


@cert_router.get("/verify/{code}/og-image.png", response_class=Response)
def certificate_og_image_png(code: str, db: Session = Depends(get_db)):
    from models import LiveSession, Organization
    from PIL import Image, ImageDraw, ImageFont
    import os as _os
    import reportlab as _rl

    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = f"Attended · {sess.title}" if sess else "Live Session Attendance"
    elif c.type == "QUALIFICATION" and c.learning_path_id:
        from models import LearningPath
        from services.pathway_service import _meta
        _p = db.query(LearningPath).filter(
            LearningPath.id == c.learning_path_id).first()
        title = (_meta(_p).get("designation") or _p.title) if _p else "IFPI Qualification"
    else:
        title = c.course.title if c.course else "IFPI Certificate"
    recipient = (c.user.name if c.user and c.user.name else "A learner")
    org_name = "IFPI Learning"
    if c.user and c.user.organization_id:
        org = db.query(Organization).filter(Organization.id == c.user.organization_id).first()
        if org:
            org_name = org.name

    def _fit(s: str, n: int) -> str:
        return s if len(s) <= n else s[:n - 1].rstrip() + "…"
    title, recipient, org_name = _fit(title, 52), _fit(recipient, 36), _fit(org_name, 40)

    fonts_dir = _os.path.join(_os.path.dirname(_rl.__file__), "fonts")
    def _font(name: str, size: int):
        try:
            return ImageFont.truetype(_os.path.join(fonts_dir, name), size)
        except Exception:
            return ImageFont.load_default()

    W, H = 1200, 630
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bot = (238, 242, 255), (237, 233, 254)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(
            round(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    d.rounded_rectangle([60, 80, 1140, 550], radius=24, fill=(255, 255, 255))
    r1, r2 = (99, 102, 241), (139, 92, 246)
    for x in range(60, 1140):
        t = (x - 60) / 1080
        d.line([(x, 80), (x, 88)], fill=tuple(
            round(r1[i] + (r2[i] - r1[i]) * t) for i in range(3)))

    def _center(text, y, font, fill):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)

    _center("CERTIFICATE OF ACHIEVEMENT", 172, _font("VeraBd.ttf", 26), (99, 102, 241))
    _center(recipient, 240, _font("VeraBd.ttf", 52), (30, 41, 59))
    _center("has successfully completed", 335, _font("Vera.ttf", 21), (100, 116, 139))
    _center(title, 385, _font("VeraBd.ttf", 32), (67, 56, 202))
    _center(f"Awarded by {org_name}", 460, _font("Vera.ttf", 18), (148, 163, 184))
    _center(f"verify: {code}", 505, _font("Vera.ttf", 14), (203, 213, 225))

    if c.revoked_at:
        band = Image.new("RGBA", (W, 120), (220, 38, 38, 235))
        img.paste(band, (0, 200), band)
        f = _font("VeraBd.ttf", 68)
        w = d.textlength("REVOKED", font=f)
        d.text(((W - w) / 2, 225), "REVOKED", font=f, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return Response(buf.getvalue(), media_type="image/png", headers={
        "Cache-Control": "public, max-age=300" if c.revoked_at
                         else "public, max-age=86400",
    })


@cert_router.get("/{cert_id}/pdf")
def download_certificate_pdf(
    cert_id: int, request: Request, db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    from models import Organization, LiveSession
    from services.pdf_certificate_service import render_certificate
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user_id != current.id and not current.has_any_role({"ADMIN", "SUPER_ADMIN"}):
        raise HTTPException(status_code=403, detail="Forbidden")
    if c.revoked_at and not current.has_any_role({"ADMIN", "SUPER_ADMIN"}):
        raise HTTPException(status_code=410, detail="Certificate has been revoked")
    base = str(request.base_url).rstrip("/")
    verify_url = f"{base}/verify/{c.code}"
    org = db.query(Organization).filter(Organization.id == c.user.organization_id).first() if c.user else None

    footer_override = None
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = sess.title if sess else "Live Session"
        cert_type = "Live Session Attendance"
    elif c.type == "QUALIFICATION" and c.learning_path_id:
        from models import LearningPath
        from services.pathway_service import _meta
        p = db.query(LearningPath).filter(
            LearningPath.id == c.learning_path_id).first()
        meta = _meta(p) if p else {}
        title = meta.get("designation") or (p.title if p else "IFPI Qualification")
        parts = ["Qualification"]
        if meta.get("nqf_level"):
            parts.append(f"NQF Level {meta['nqf_level']}")
        if meta.get("total_credits"):
            parts.append(f"{meta['total_credits']} Credits")
        cert_type = " · ".join(parts)
        if meta.get("unit_standards"):
            footer_override = "Unit Standards: " + "; ".join(
                us.split(" — ")[0] for us in meta["unit_standards"])
    else:
        title = c.course.title if c.course else "IFPI Course"
        cert_type = "Course Completion" if c.type == "COURSE_COMPLETION" else c.type.replace("_", " ").title()

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
            footer_text=footer_override or (org.cert_footer_text if org else None),
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


# ── Transcript (migrated from iter8.py) ──────────────────────────────
@cert_router.get("/transcript.json")
def my_transcript_json(db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    """Iter 50 — JSON payload behind the printable transcript page."""
    from models import LiveSession
    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    enrolls = db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.status == EnrollmentStatus.COMPLETED,
    ).all()
    courses = {c.id: c for c in db.query(Course).filter(
        Course.id.in_([e.course_id for e in enrolls])).all()}
    attempt_rows = db.query(ExamAttempt, Exam.course_id).join(
        Exam, Exam.id == ExamAttempt.exam_id).filter(
        ExamAttempt.user_id == user.id, ExamAttempt.score.isnot(None),
    ).all()
    best_score: dict[int, float] = {}
    for a, cid in attempt_rows:
        if cid and (cid not in best_score or a.score > best_score[cid]):
            best_score[cid] = a.score
    certs = db.query(Certificate).filter(
        Certificate.user_id == user.id,
    ).order_by(Certificate.issued_at.desc()).all()
    session_titles = {}
    sess_ids = [c.live_session_id for c in certs if c.live_session_id]
    if sess_ids:
        session_titles = {s.id: s.title for s in db.query(LiveSession).filter(
            LiveSession.id.in_(sess_ids)).all()}
    from models import UserBadge
    badges = db.query(UserBadge).filter(UserBadge.user_id == user.id).order_by(
        UserBadge.earned_at.asc()).all()
    return {
        "learner": {"name": user.name, "email": user.email,
                    "cohort": user.cohort, "total_xp": user.points or 0},
        "organization": {"name": org.name if org else "IFPI Learning",
                         "primary_color": (org.primary_color if org else None) or "#6366f1",
                         "logo_url": org.logo_url if org else None},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "courses": [{
            "id": e.course_id,
            "title": courses[e.course_id].title,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "best_score": best_score.get(e.course_id),
        } for e in enrolls if e.course_id in courses],
        "certificates": [{
            "id": c.id, "code": c.code, "type": c.type,
            "title": (c.course.title if c.course
                      else session_titles.get(c.live_session_id, "Certificate")),
            "issued_at": c.issued_at.isoformat() if c.issued_at else None,
            "revoked": c.revoked_at is not None,
        } for c in certs],
        "badges": [{
            "badge": b.badge,
            "earned_at": b.earned_at.isoformat() if b.earned_at else None,
        } for b in badges],
    }


@cert_router.get("/transcript")
def my_transcript(db: Session = Depends(get_db),
                  current: CurrentUser = Depends(get_current_user)):
    """Generate a branded PDF transcript for the calling user."""
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    enrolls = db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.status == EnrollmentStatus.COMPLETED,
    ).all()
    courses = {c.id: c for c in db.query(Course).filter(
        Course.id.in_([e.course_id for e in enrolls])).all()}
    from models import Exam
    attempt_rows = db.query(ExamAttempt, Exam.course_id).join(Exam, Exam.id == ExamAttempt.exam_id).filter(
        ExamAttempt.user_id == user.id, ExamAttempt.score.isnot(None),
    ).order_by(ExamAttempt.completed_at.desc().nullslast()).all()
    best_score_per_course: dict[int, float] = {}
    for a, cid in attempt_rows:
        if cid and (cid not in best_score_per_course or a.score > best_score_per_course[cid]):
            best_score_per_course[cid] = a.score
    from models import UserBadge
    badges = db.query(UserBadge).filter(UserBadge.user_id == user.id).order_by(UserBadge.earned_at.asc()).all()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    accent = HexColor(org.primary_color or "#6366f1") if org else HexColor("#6366f1")
    c.setFillColor(accent); c.rect(0, H - 3.2*cm, W, 3.2*cm, fill=1, stroke=0)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 22)
    c.drawString(2*cm, H - 2.1*cm, "Learner Transcript")
    c.setFont("Helvetica", 11)
    c.drawString(2*cm, H - 2.8*cm, (org.name if org else "IFPI Learning"))

    y = H - 4.5*cm
    c.setFillColor(HexColor("#0f172a")); c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, y, user.name or user.email)
    c.setFont("Helvetica", 9); c.setFillColor(HexColor("#64748b"))
    y -= 0.5*cm; c.drawString(2*cm, y, f"Email: {user.email}")
    if user.cohort:
        y -= 0.4*cm; c.drawString(2*cm, y, f"Cohort: {user.cohort}")
    y -= 0.4*cm; c.drawString(2*cm, y, f"Total XP: {user.points or 0}")
    y -= 0.4*cm; c.drawString(2*cm, y, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

    y -= 0.9*cm
    c.setFillColor(accent); c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Completed courses")
    y -= 0.2*cm; c.setStrokeColor(accent); c.line(2*cm, y, W - 2*cm, y); y -= 0.4*cm
    c.setFont("Helvetica", 10); c.setFillColor(HexColor("#0f172a"))
    if not enrolls:
        c.setFillColor(HexColor("#94a3b8")); c.drawString(2*cm, y, "— no courses completed yet —"); y -= 0.5*cm
    for e in enrolls:
        course = courses.get(e.course_id)
        if not course:
            continue
        date = e.completed_at.strftime("%Y-%m-%d") if e.completed_at else "—"
        score = best_score_per_course.get(course.id)
        score_str = f"{score:.0f}%" if score is not None else "n/a"
        c.setFillColor(HexColor("#0f172a")); c.drawString(2*cm, y, f"• {course.title}")
        c.setFillColor(HexColor("#64748b")); c.drawRightString(W - 2*cm, y, f"{date}   Score: {score_str}")
        y -= 0.5*cm
        if y < 3*cm:
            c.showPage(); y = H - 2*cm

    if badges:
        y -= 0.4*cm
        c.setFillColor(accent); c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y, "Badges earned")
        y -= 0.2*cm; c.line(2*cm, y, W - 2*cm, y); y -= 0.4*cm
        c.setFont("Helvetica", 10); c.setFillColor(HexColor("#0f172a"))
        for b in badges:
            date = b.earned_at.strftime("%Y-%m-%d") if b.earned_at else ""
            c.drawString(2*cm, y, f"• {b.badge}")
            c.setFillColor(HexColor("#64748b")); c.drawRightString(W - 2*cm, y, date)
            c.setFillColor(HexColor("#0f172a"))
            y -= 0.5*cm
            if y < 3*cm:
                c.showPage(); y = H - 2*cm

    c.setFont("Helvetica-Oblique", 7); c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(W/2, 1.2*cm,
        f"Issued by {org.name if org else 'IFPI Learning'} · This document does not constitute a certificate of credit unless accompanied by individual course certificates.")
    c.showPage(); c.save()
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=transcript_{user.id}.pdf"},
    )
