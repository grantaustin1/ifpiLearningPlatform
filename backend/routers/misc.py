"""Misc routes: AI builder, enrollments, certificates, notifications, leaderboard, analytics, billing, public catalog."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import ADMIN_ROLES
from models import (
    Certificate, Course, CourseStatus, Enrollment, EnrollmentStatus, Exam,
    ExamAttempt, Notification, Subscription, User, UserBadge,
)
from schemas import (
    AIBuilderRequest, AIBuilderResponse, AnalyticsOverview, CertificateOut,
    CourseSummary, EnrollmentOut, LeaderboardEntry, NotificationOut,
    SubscribeRequest, SubscribeResponse, SubscriptionOut,
)
from services.ai_builder_service import generate_course
from services.billing_service import BillingService
from services.gamification_service import BADGE_META

logger = logging.getLogger(__name__)


# ── AI builder ───────────────────────────────────────────────────────
ai_router = APIRouter(prefix="/api/ai", tags=["AI"])


@ai_router.post("/course-builder", response_model=AIBuilderResponse)
async def ai_course_builder(
    body: AIBuilderRequest,
    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")),
):
    result = await generate_course(
        topic=body.topic, description=body.description or "",
        num_slides=body.num_slides, include_quiz=body.include_quiz,
        num_questions=body.num_questions,
    )
    return AIBuilderResponse(**result)


# ── Enrollments ──────────────────────────────────────────────────────
enroll_router = APIRouter(prefix="/api/enrollments", tags=["Enrollments"])


@enroll_router.get("", response_model=List[EnrollmentOut])
def my_enrollments(db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)):
    rows = db.query(Enrollment).filter(
        Enrollment.user_id == current.id,
    ).order_by(Enrollment.enrolled_at.desc()).all()
    out = []
    for e in rows:
        out.append(EnrollmentOut(
            id=e.id, course_id=e.course_id, course_title=e.course.title,
            status=e.status.value, progress=e.progress,
            enrolled_at=e.enrolled_at, completed_at=e.completed_at,
        ))
    return out


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
    return [CertificateOut(
        id=c.id, code=c.code, type=c.type,
        course_title=c.course.title if c.course else None,
        issued_at=c.issued_at, score=c.score,
    ) for c in rows]


@cert_router.get("/verify/{code}")
def verify_certificate(code: str, db: Session = Depends(get_db)):
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return {
        "valid": True, "code": c.code, "type": c.type,
        "recipient_name": c.user.name if c.user else None,
        "course_title": c.course.title if c.course else None,
        "issued_at": c.issued_at,
    }


@cert_router.get("/{cert_id}/pdf")
def download_certificate_pdf(
    cert_id: int, request: Request, db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Generate a branded PDF for a certificate. Owner or admin only."""
    from models import Organization
    from services.pdf_certificate_service import render_certificate
    c = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.user_id != current.id and not current.has_any_role({"ADMIN", "SUPER_ADMIN"}):
        raise HTTPException(status_code=403, detail="Forbidden")
    base = str(request.base_url).rstrip("/")
    verify_url = f"{base}/verify/{c.code}"
    org = db.query(Organization).filter(Organization.id == c.user.organization_id).first() if c.user else None
    pdf = render_certificate(
        recipient_name=c.user.name or c.user.email,
        course_title=c.course.title if c.course else "IFPI Course",
        certificate_code=c.code,
        issued_at=c.issued_at,
        verify_url=verify_url,
        score=c.score,
        cert_type="Course Completion" if c.type == "COURSE_COMPLETION" else c.type.replace("_", " ").title(),
        organisation_name=org.name if org else "IFPI Learning",
        organisation_logo_url=org.logo_url if org else None,
        accent_color=(org.cert_accent_color or org.primary_color or "#6366f1") if org else "#6366f1",
        signature_text=org.cert_signature_text if org else None,
        signature_image_url=org.cert_signature_image_url if org else None,
        footer_text=org.cert_footer_text if org else None,
    )
    filename = f"IFPI-Certificate-{c.code}.pdf"
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Notifications ────────────────────────────────────────────────────
notif_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@notif_router.get("")
def list_notifications(db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    rows = db.query(Notification).filter(
        Notification.user_id == current.id,
    ).order_by(Notification.created_at.desc()).limit(25).all()
    unread = sum(1 for n in rows if not n.is_read)
    return {
        "notifications": [NotificationOut.model_validate(n).model_dump() for n in rows],
        "unread_count": unread,
    }


@notif_router.patch("/read-all")
def mark_all_read(db: Session = Depends(get_db),
                  current: CurrentUser = Depends(get_current_user)):
    db.query(Notification).filter(
        Notification.user_id == current.id, Notification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ── Leaderboard & gamification ───────────────────────────────────────
gam_router = APIRouter(prefix="/api/gamification", tags=["Gamification"])


@gam_router.get("/leaderboard", response_model=List[LeaderboardEntry])
def leaderboard(cohort: Optional[str] = None,
                db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    q = db.query(User).filter(
        User.organization_id == current.organization_id, User.is_active.is_(True),
    )
    if cohort:
        q = q.filter(User.cohort == cohort)
    rows = q.order_by(desc(User.points)).limit(50).all()
    out = []
    for u in rows:
        completed = sum(1 for e in u.enrollments if e.status == EnrollmentStatus.COMPLETED)
        out.append(LeaderboardEntry(
            user_id=u.id, name=u.name, points=u.points or 0,
            badges=len(u.badges), completed=completed,
        ))
    return out


@gam_router.get("/me")
def my_gamification(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current.id).first()
    # Resolve badge meta from per-org BadgeTier rows (with global fallback)
    from models import BadgeTier
    tiers = {t.slug: t for t in db.query(BadgeTier).filter(
        BadgeTier.organization_id == current.organization_id,
        BadgeTier.is_active.is_(True),
    ).all()}
    def _meta(slug: str) -> dict:
        t = tiers.get(slug)
        if t:
            return {"label": t.label, "emoji": t.emoji or "🏅", "desc": t.description or ""}
        return BADGE_META.get(slug, {"label": slug, "emoji": "🏅", "desc": ""})
    badges = [{
        "badge": b.badge, "earned_at": b.earned_at, "meta": _meta(b.badge),
    } for b in user.badges]
    rank = db.query(User).filter(
        User.organization_id == current.organization_id,
        User.points > (user.points or 0),
    ).count() + 1
    total = db.query(User).filter(
        User.organization_id == current.organization_id, User.is_active.is_(True),
    ).count()
    return {"points": user.points or 0, "badges": badges, "rank": rank, "total": total}


# ── Analytics (admin) ────────────────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])


@admin_router.get("/analytics", response_model=AnalyticsOverview)
def analytics(db: Session = Depends(get_db),
              current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    org = current.organization_id
    total_learners = db.query(User).filter(User.organization_id == org).count()
    total_courses = db.query(Course).filter(Course.organization_id == org).count()
    total_enrollments = db.query(Enrollment).join(Course).filter(Course.organization_id == org).count()
    completed = db.query(Enrollment).join(Course).filter(
        Course.organization_id == org, Enrollment.status == EnrollmentStatus.COMPLETED,
    ).count()
    completion_rate = round((completed / total_enrollments) * 100) if total_enrollments else 0
    total_certificates = db.query(Certificate).join(User).filter(User.organization_id == org).count()

    attempts = db.query(ExamAttempt).join(Exam).filter(Exam.organization_id == org).all()
    avg_score = round(sum(a.score for a in attempts) / len(attempts)) if attempts else 0

    # Monthly enrollments — last 6 months via Python (DB-agnostic; avoids DATE_TRUNC)
    from collections import OrderedDict
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    months = OrderedDict()
    for i in range(5, -1, -1):
        y = now.year + ((now.month - i - 1) // 12)
        m = ((now.month - i - 1) % 12) + 1
        months[f"{y}-{m:02d}"] = 0
    enrolls = db.query(Enrollment).join(Course).filter(Course.organization_id == org).all()
    for e in enrolls:
        key = f"{e.enrolled_at.year}-{e.enrolled_at.month:02d}"
        if key in months:
            months[key] += 1
    monthly = [{"month": k, "count": v} for k, v in months.items()]

    # Top courses by enrolment
    top_q = db.query(Course, func.count(Enrollment.id).label("c")).outerjoin(Enrollment).filter(
        Course.organization_id == org,
    ).group_by(Course.id).order_by(desc("c")).limit(8).all()
    top_courses = []
    for c, total in top_q:
        comp = sum(1 for e in c.enrollments if e.status == EnrollmentStatus.COMPLETED)
        top_courses.append({
            "id": c.id, "title": c.title, "total": total,
            "completed": comp,
            "rate": round((comp / total) * 100) if total else 0,
        })

    recents = db.query(Enrollment).join(Course).filter(
        Course.organization_id == org,
    ).order_by(desc(Enrollment.enrolled_at)).limit(8).all()
    recent_activity = [{
        "user_name": e.user.name or "Learner", "course_title": e.course.title,
        "status": e.status.value, "progress": e.progress,
        "enrolled_at": e.enrolled_at,
    } for e in recents]

    return AnalyticsOverview(
        total_learners=total_learners, total_courses=total_courses,
        total_enrollments=total_enrollments, completion_rate=completion_rate,
        total_certificates=total_certificates,
        total_exam_attempts=len(attempts), avg_exam_score=avg_score,
        monthly_enrollments=monthly, top_courses=top_courses,
        recent_activity=recent_activity,
    )


@admin_router.get("/users")
def list_users(db: Session = Depends(get_db),
               current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(User).filter(
        User.organization_id == current.organization_id,
    ).order_by(User.created_at.desc()).all()
    return [{
        "id": u.id, "email": u.email, "name": u.name,
        "roles": [ur.role for ur in u.user_roles],
        "points": u.points or 0, "enrollments": len(u.enrollments),
        "completed": sum(1 for e in u.enrollments if e.status == EnrollmentStatus.COMPLETED),
        "certificates": len(u.certificates), "created_at": u.created_at,
        "is_active": u.is_active,
    } for u in rows]


# ── Billing ──────────────────────────────────────────────────────────
billing_router = APIRouter(prefix="/api/billing", tags=["Billing"])


@billing_router.post("/subscribe", response_model=SubscribeResponse)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db),
              current: CurrentUser = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current.id).first()
    course = db.query(Course).filter(
        Course.id == body.course_id, Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    result = BillingService(db).subscribe(user, course)
    return SubscribeResponse(**result)


@billing_router.get("/subscriptions", response_model=List[SubscriptionOut])
def my_subscriptions(db: Session = Depends(get_db),
                     current: CurrentUser = Depends(get_current_user)):
    rows = db.query(Subscription).filter(
        Subscription.user_id == current.id,
    ).order_by(Subscription.created_at.desc()).all()
    return rows


@billing_router.post("/webhook")
async def billing_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives ERP360 billing webhooks. Verified via X-Signature header."""
    body = await request.body()
    sig = request.headers.get("X-Signature") or request.headers.get("x-signature")
    svc = BillingService(db)
    if not svc.verify_webhook_signature(body, sig):
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    event_type = data.get("type") or data.get("event_type") or "unknown"
    return svc.handle_event(event_type, data.get("data") or data)


# ── Public catalog (no auth) ─────────────────────────────────────────
catalog_router = APIRouter(prefix="/api/catalog", tags=["Catalog"])


@catalog_router.get("")
def catalog(q: str | None = Query(None),
            category: str | None = Query(None),
            featured: bool = Query(False),
            sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|most_enrolled)$"),
            page: int = Query(1, ge=1),
            page_size: int = Query(24, ge=1, le=100),
            db: Session = Depends(get_db)):
    from models import Organization, Enrollment
    from sqlalchemy import func
    query = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
    )
    if q:
        query = query.filter(Course.title.ilike(f"%{q}%"))
    if category:
        query = query.filter(Course.category == category)
    total = query.count()
    if featured:
        # Featured = top 6 by enrollment count (SQL-side)
        enroll_sq = (
            db.query(Enrollment.course_id, func.count(Enrollment.id).label("n"))
            .group_by(Enrollment.course_id).subquery()
        )
        courses = (
            query.outerjoin(enroll_sq, enroll_sq.c.course_id == Course.id)
                 .order_by(func.coalesce(enroll_sq.c.n, 0).desc(), Course.created_at.desc())
                 .limit(6).all()
        )
    else:
        # Apply sort
        if sort == "price_asc":
            query = query.order_by(Course.price_cents.asc(), Course.created_at.desc())
        elif sort == "price_desc":
            query = query.order_by(Course.price_cents.desc(), Course.created_at.desc())
        elif sort == "most_enrolled":
            enroll_sq = (
                db.query(Enrollment.course_id, func.count(Enrollment.id).label("n"))
                .group_by(Enrollment.course_id).subquery()
            )
            query = (query.outerjoin(enroll_sq, enroll_sq.c.course_id == Course.id)
                          .order_by(func.coalesce(enroll_sq.c.n, 0).desc(),
                                    Course.created_at.desc()))
        else:  # newest
            query = query.order_by(Course.created_at.desc())
        courses = query.offset((page - 1) * page_size).limit(page_size).all()
    # Bulk-load orgs for the resulting courses
    org_ids = {c.organization_id for c in courses}
    orgs = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}
    cats = [r[0] for r in db.query(Course.category).filter(
        Course.status == CourseStatus.PUBLISHED, Course.category.isnot(None),
    ).distinct().all() if r[0]]
    return {
        "courses": [{
            "id": c.id, "title": c.title, "description": c.description,
            "category": c.category, "cover_color": c.cover_color,
            "duration_minutes": c.duration_minutes, "price_cents": c.price_cents,
            "currency": c.currency, "slide_count": len(c.slides),
            "enrollment_count": len(c.enrollments),
            "organization": ({
                "id": orgs[c.organization_id].id,
                "name": orgs[c.organization_id].name,
                "logo_url": orgs[c.organization_id].logo_url,
            } if c.organization_id in orgs else None),
        } for c in courses],
        "categories": cats,
        "total": total, "page": page, "page_size": page_size,
        "sort": sort,
    }


@catalog_router.get("/{course_id}")
def catalog_detail(course_id: int, db: Session = Depends(get_db)):
    """Public course detail — shown on marketplace product page."""
    from models import Organization
    course = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.id == course_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or not publicly listed")
    org = db.query(Organization).filter(Organization.id == course.organization_id).first()
    slides = sorted(course.slides, key=lambda s: s.order_index)[:8]
    return {
        "id": course.id, "title": course.title, "description": course.description,
        "category": course.category, "cover_color": course.cover_color,
        "duration_minutes": course.duration_minutes, "price_cents": course.price_cents,
        "currency": course.currency,
        "slide_count": len(course.slides),
        "enrollment_count": len(course.enrollments),
        "syllabus_preview": [{"title": s.title, "order_index": s.order_index} for s in slides],
        "organization": {
            "id": org.id, "name": org.name, "logo_url": org.logo_url,
        } if org else None,
    }
