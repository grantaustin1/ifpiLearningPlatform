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
    c.revoked_at = _dt.now(_tz.utc)
    c.revoked_reason = reason
    db.commit()
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
    c.revoked_at = None
    c.revoked_reason = None
    db.commit()
    return {"revoked": False, "code": c.code}


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

    pdf = render_certificate(
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


@gam_router.get("/learning-streak")
def learning_streak(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 26 — Consecutive-day learning streak. A day counts when the
    learner viewed a course slide OR reviewed a flashcard. Returns
    `{current_streak, longest_streak, active_today, last_active_date}`."""
    from services.gamification_service import GamificationService
    return GamificationService(db).compute_learning_streak(current.id)


@gam_router.get("/streak-leaderboard")
def streak_leaderboard(
    limit: int = 10,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 28 — Org-wide "top streaks this week" leaderboard.

    Ranks the top `limit` learners in the caller's organisation by
    current streak (descending). Ties break on longest_streak, then
    user id. Includes the caller's own rank at the bottom even if
    they're outside the top N.

    Cheap enough to compute on the fly for orgs up to a few hundred
    active users (SlideView + FlashcardReview joins are already
    indexed). For much larger orgs, pre-computing in a nightly job
    would be advisable — but iter-28 scope is small orgs.
    """
    from services.gamification_service import GamificationService
    limit = max(1, min(limit, 50))
    gam = GamificationService(db)
    users = db.query(User).filter(
        User.organization_id == current.organization_id,
        User.is_active == True,  # noqa: E712
    ).all()

    entries = []
    for u in users:
        try:
            s = gam.compute_learning_streak(u.id)
        except Exception:
            continue
        if s["current_streak"] <= 0 and s["longest_streak"] <= 0:
            continue  # skip users with no activity — cleaner UX
        entries.append({
            "user_id": u.id,
            "name": u.name or u.email.split("@")[0],
            "avatar_url": None,  # Iter 29 backlog — org-scoped avatars
            "current_streak": s["current_streak"],
            "longest_streak": s["longest_streak"],
            "active_today": s["active_today"],
            "is_you": u.id == current.id,
        })
    entries.sort(key=lambda e: (
        -e["current_streak"], -e["longest_streak"], e["user_id"],
    ))

    top = entries[:limit]
    caller_rank = next(
        (i + 1 for i, e in enumerate(entries) if e["user_id"] == current.id),
        None,
    )
    return {
        "top": top,
        "your_rank": caller_rank,
        "your_entry": next((e for e in entries if e["is_you"]), None),
        "total_participants": len(entries),
    }


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


@catalog_router.get("/organizations")
def catalog_organizations(db: Session = Depends(get_db)):
    """Iter 27 — Cross-tenant marketplace search: list opted-in
    organizations with a public course. Powers the org-filter dropdown
    on the marketplace catalog page."""
    from models import Organization
    from sqlalchemy import func
    rows = (
        db.query(
            Organization.id, Organization.name, Organization.logo_url,
            func.count(Course.id).label("course_count"),
        )
        .join(Course, Course.organization_id == Organization.id)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .filter(Course.status == CourseStatus.PUBLISHED)
        .group_by(Organization.id, Organization.name, Organization.logo_url)
        .order_by(func.count(Course.id).desc(), Organization.name.asc())
        .all()
    )
    return [
        {"id": r.id, "name": r.name, "logo_url": r.logo_url,
         "course_count": r.course_count}
        for r in rows
    ]


@catalog_router.get("")
def catalog(q: str | None = Query(None),
            category: str | None = Query(None),
            org: int | None = Query(None, description="Filter by organization id (Iter 27)"),
            featured: bool = Query(False),
            sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|most_enrolled)$"),
            page: int = Query(1, ge=1),
            page_size: int = Query(24, ge=1, le=100),
            db: Session = Depends(get_db)):
    from models import Organization, Enrollment
    from sqlalchemy import func, or_
    query = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
    )
    if q:
        # Iter 27 — Cross-tenant search: match on course title
        # OR organization name so a search for "IFPI" surfaces
        # courses published by "IFPI Academy" etc.
        like = f"%{q}%"
        query = query.filter(or_(
            Course.title.ilike(like),
            Organization.name.ilike(like),
        ))
    if category:
        query = query.filter(Course.category == category)
    if org is not None:
        query = query.filter(Course.organization_id == org)
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
