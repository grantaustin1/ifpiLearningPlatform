from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import Certificate

from . import cert_router
from ._schemas import BulkEmailIn, BulkZipIn


@cert_router.post("/bulk-email")
def bulk_email_certificates(
    body: BulkEmailIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Iter 31 — Bulk re-email certificate download links to owners.
    Useful for resending after infra issues or re-notifying learners
    of a re-issued cert. Uses standard outbox pipeline."""
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
