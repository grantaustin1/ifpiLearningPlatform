"""Enrollment domain service — business logic for enroll, progress and
course completion, extracted from the router layer (audit P1: fat controllers)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser
from models import (
    Course, CourseSlide, CourseStatus, Enrollment, EnrollmentStatus,
)


class EnrollmentService:
    def __init__(self, db: Session):
        self.db = db

    def enroll(self, current: CurrentUser, course_id: int) -> dict:
        db = self.db
        from services.gamification_service import (
            XP_FIRST_ENROLLMENT, GamificationService,
        )
        from services.prerequisite_service import get_unmet_prerequisites
        c = db.query(Course).filter(
            Course.id == course_id, Course.organization_id == current.organization_id,
            Course.status == CourseStatus.PUBLISHED,
        ).first()
        if not c:
            raise HTTPException(status_code=404, detail="Course not found or not published")
        unmet = get_unmet_prerequisites(db, current.id, course_id)
        if unmet:
            raise HTTPException(
                status_code=412,
                detail={
                    "message": "Complete prerequisite courses first",
                    "missing": [{"id": cid, "title": title} for cid, title in unmet],
                },
            )
        if c.price_cents > 0:
            # §7.1 — enrollment code must NOT branch on billing_mode.
            from services.entitlement_service import require_course_entitlement
            require_course_entitlement(db, current.id, c)
        existing = db.query(Enrollment).filter(
            Enrollment.user_id == current.id, Enrollment.course_id == course_id,
        ).first()
        if existing:
            return {"ok": True, "enrollment_id": existing.id, "already": True,
                    "last_slide_index": existing.last_slide_index or 0}
        from sqlalchemy.exc import IntegrityError
        e = Enrollment(user_id=current.id, course_id=course_id)
        db.add(e)
        try:
            db.flush()
        except IntegrityError:
            # Race: a concurrent request enrolled first — behave idempotently.
            db.rollback()
            existing = db.query(Enrollment).filter(
                Enrollment.user_id == current.id, Enrollment.course_id == course_id,
            ).first()
            return {"ok": True, "enrollment_id": existing.id if existing else None,
                    "already": True,
                    "last_slide_index": (existing.last_slide_index if existing else 0) or 0}
        gam = GamificationService(db)
        gam.award_xp(current.id, XP_FIRST_ENROLLMENT)
        enroll_count = db.query(Enrollment).filter(Enrollment.user_id == current.id).count()
        if enroll_count == 1:
            gam.award_badge(current.id, "FIRST_ENROLLMENT")
        db.commit()
        return {"ok": True, "enrollment_id": e.id, "already": False, "last_slide_index": 0}

    def save_progress(self, current: CurrentUser, course_id: int, slide_index: int) -> dict:
        db = self.db
        e = db.query(Enrollment).filter(
            Enrollment.user_id == current.id, Enrollment.course_id == course_id,
        ).first()
        if not e:
            raise HTTPException(status_code=404, detail="Not enrolled")
        total = db.query(CourseSlide).filter(CourseSlide.course_id == course_id).count()
        idx = max(0, min(slide_index, max(total - 1, 0)))
        e.last_slide_index = idx
        if total and e.status != EnrollmentStatus.COMPLETED:
            e.progress = max(e.progress or 0.0, round((idx + 1) / total * 100, 1))
        db.commit()
        return {"ok": True, "last_slide_index": idx, "progress": e.progress}

    def complete(self, current: CurrentUser, course_id: int, base_url: str) -> dict:
        db = self.db
        from models import Certificate, Organization
        from services.gamification_service import (
            XP_COURSE_COMPLETE, GamificationService,
        )
        from services.mail_service import MailService
        from services.pdf_certificate_service import render_certificate

        c = db.query(Course).filter(
            Course.id == course_id, Course.organization_id == current.organization_id,
        ).first()
        if not c:
            raise HTTPException(status_code=404, detail="Course not found")

        e = db.query(Enrollment).filter(
            Enrollment.user_id == current.id, Enrollment.course_id == course_id,
        ).first()
        already = e is not None and e.status == EnrollmentStatus.COMPLETED
        if not e:
            e = Enrollment(user_id=current.id, course_id=course_id)
            db.add(e)
            db.flush()
        e.status = EnrollmentStatus.COMPLETED
        e.progress = 100.0
        e.completed_at = datetime.now(timezone.utc)

        cert = db.query(Certificate).filter(
            Certificate.user_id == current.id, Certificate.course_id == course_id,
        ).first()
        cert_is_new = cert is None
        if cert_is_new:
            cert = Certificate(user_id=current.id, course_id=course_id,
                               type="COURSE_COMPLETION")
            db.add(cert)
            db.flush()

        if already:
            db.commit()
            return {"ok": True, "xp_earned": 0, "badges_earned": [],
                    "already_completed": True}

        gam = GamificationService(db)
        gam.award_xp(current.id, XP_COURSE_COMPLETE)
        gam.notify(current.id, "COURSE_COMPLETE",
                   f"🎓 Completed: {c.title}",
                   f"You earned {XP_COURSE_COMPLETE} XP and a certificate!",
                   "/certificates")
        completed = db.query(Enrollment).filter(
            Enrollment.user_id == current.id,
            Enrollment.status == EnrollmentStatus.COMPLETED,
        ).count()
        badges = []
        if completed == 1 and gam.award_badge(current.id, "FIRST_COURSE"):
            badges.append("FIRST_COURSE")
        if completed >= 5 and gam.award_badge(current.id, "COURSE_MASTER"):
            badges.append("COURSE_MASTER")

        # Qualification tracks — award track certs when the last course lands
        quals: list = []
        try:
            from services.pathway_service import check_and_award_qualifications
            quals = check_and_award_qualifications(db, current)
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning("Qualification check failed: %s", ex)

        # Email the cert PDF (stub mode persists to outbox)
        if cert_is_new:
            try:
                from models import User
                user = db.query(User).filter(User.id == current.id).first()
                org = db.query(Organization).filter(
                    Organization.id == current.organization_id).first()
                verify_url = f"{base_url.rstrip('/')}/verify/{cert.code}"
                pdf_bytes = render_certificate(
                    recipient_name=user.name or user.email,
                    course_title=c.title, certificate_code=cert.code,
                    issued_at=cert.issued_at, verify_url=verify_url,
                    organisation_name=org.name if org else "IFPI Learning",
                    organisation_logo_url=org.logo_url if org else None,
                    accent_color=(org.cert_accent_color or org.primary_color
                                  or "#6366f1") if org else "#6366f1",
                    signature_text=org.cert_signature_text if org else None,
                    signature_image_url=org.cert_signature_image_url if org else None,
                    footer_text=org.cert_footer_text if org else None,
                )
                MailService(db).send_email(
                    to_email=user.email, to_name=user.name,
                    subject=f"🎓 Your certificate for {c.title}",
                    body_html=_cert_email_html(user.name or "there", c.title, verify_url),
                    template="cert_issued", organization_id=current.organization_id,
                    user_id=current.id,
                    attachments=[{
                        "filename": f"IFPI-Certificate-{cert.code}.pdf",
                        "mime": "application/pdf", "content": pdf_bytes,
                    }],
                )
            except Exception as ex:
                import logging
                logging.getLogger(__name__).warning("Cert email queue failed: %s", ex)
        db.commit()

        # Outgoing webhooks — fire AFTER commit so the receiver never sees an
        # event for a row that subsequently rolled back. emit_safely never raises.
        from services.webhook_service import emit_safely
        emit_safely(db, current.organization_id, "course.completed", {
            "user_id": current.id, "user_email": current.email,
            "erp360_user_id": getattr(current, "erp360_user_id", None),
            "course_id": c.id, "course_title": c.title,
            "completed_at": (e.completed_at or datetime.now(timezone.utc)).isoformat(),
            "xp_earned": XP_COURSE_COMPLETE, "badges_earned": badges,
        })
        if cert_is_new:
            emit_safely(db, current.organization_id, "certificate.issued", {
                "user_id": current.id, "user_email": current.email,
                "erp360_user_id": getattr(current, "erp360_user_id", None),
                "course_id": c.id, "course_title": c.title,
                "certificate_code": cert.code,
                "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
            })
        return {"ok": True, "xp_earned": XP_COURSE_COMPLETE, "badges_earned": badges,
                "qualifications_earned": quals}


def _cert_email_html(name: str, course_title: str, verify_url: str) -> str:
    return f"""
<!DOCTYPE html><html><body style="font-family: -apple-system, system-ui, sans-serif; background: #f8fafc; padding: 32px;">
  <div style="max-width: 540px; margin: 0 auto; background: white; border-radius: 16px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.05);">
    <h1 style="margin: 0 0 8px; color: #0f172a; font-size: 22px;">🎓 Congratulations, {name}!</h1>
    <p style="color: #64748b; font-size: 14px; line-height: 1.6; margin: 0 0 16px;">
      You've successfully completed <strong>{course_title}</strong>. Your certificate is attached to this email.
    </p>
    <p style="color: #64748b; font-size: 14px; line-height: 1.6;">You can also <a href="{verify_url}" style="color: #6366f1;">verify your certificate online</a>.</p>
  </div>
</body></html>
""".strip()
