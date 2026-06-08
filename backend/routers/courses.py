"""Course routes: CRUD + slide management. Role-gated at the API layer."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import ADMIN_ROLES, INSTRUCTOR_ROLES
from models import (
    Course, CourseSlide, CourseStatus, Enrollment, EnrollmentStatus,
    SlideType,
)
from schemas import (
    CourseCreate, CourseDetail, CourseSummary, CourseUpdate, SlideIn, SlideOut,
)

router = APIRouter(prefix="/api/courses", tags=["Courses"])


def _can_manage(user: CurrentUser) -> bool:
    return user.has_any_role(INSTRUCTOR_ROLES)


def _summary(c: Course) -> CourseSummary:
    return CourseSummary(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, slide_count=len(c.slides),
        enrollment_count=len(c.enrollments), created_at=c.created_at,
    )


@router.get("", response_model=List[CourseSummary])
def list_courses(
    q: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    query = db.query(Course).filter(Course.organization_id == current.organization_id)
    if not _can_manage(current):
        query = query.filter(Course.status == CourseStatus.PUBLISHED)
    if q:
        query = query.filter(Course.title.ilike(f"%{q}%"))
    if category:
        query = query.filter(Course.category == category)
    courses = query.order_by(Course.created_at.desc()).all()
    return [_summary(c) for c in courses]


@router.post("", response_model=CourseDetail)
def create_course(
    body: CourseCreate, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")),
):
    course = Course(
        organization_id=current.organization_id,
        title=body.title, description=body.description, category=body.category,
        passing_score=body.passing_score, duration_minutes=body.duration_minutes,
        price_cents=body.price_cents, currency=body.currency,
        status=CourseStatus(body.status) if body.status in CourseStatus.__members__ else CourseStatus.DRAFT,
        created_by_id=current.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return _detail(course)


def _detail(c: Course) -> CourseDetail:
    return CourseDetail(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, passing_score=c.passing_score,
        slide_count=len(c.slides), enrollment_count=len(c.enrollments),
        created_at=c.created_at,
        slides=[SlideOut(
            id=s.id, title=s.title, content=s.content or "",
            slide_type=s.slide_type.value, media_url=s.media_url,
            order_index=s.order_index, is_required=s.is_required,
        ) for s in c.slides],
    )


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, db: Session = Depends(get_db),
               current: CurrentUser = Depends(get_current_user)):
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if c.status != CourseStatus.PUBLISHED and not _can_manage(current):
        raise HTTPException(status_code=404, detail="Course not found")
    return _detail(c)


@router.patch("/{course_id}", response_model=CourseDetail)
def update_course(course_id: int, body: CourseUpdate, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] in CourseStatus.__members__:
        c.status = CourseStatus(data.pop("status"))
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _detail(c)


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Slides ─────────────────────────────────────────────────────────
@router.post("/{course_id}/slides", response_model=SlideOut)
def add_slide(course_id: int, body: SlideIn, db: Session = Depends(get_db),
              current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    next_order = (db.query(func.max(CourseSlide.order_index)).filter(
        CourseSlide.course_id == course_id,
    ).scalar() or 0) + 1
    s = CourseSlide(
        course_id=course_id, title=body.title, content=body.content or "",
        slide_type=SlideType(body.slide_type) if body.slide_type in SlideType.__members__ else SlideType.TEXT,
        media_url=body.media_url, order_index=body.order_index or next_order,
        is_required=body.is_required,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return SlideOut(
        id=s.id, title=s.title, content=s.content or "",
        slide_type=s.slide_type.value, media_url=s.media_url,
        order_index=s.order_index, is_required=s.is_required,
    )


@router.patch("/{course_id}/slides/{slide_id}", response_model=SlideOut)
def update_slide(course_id: int, slide_id: int, body: SlideIn, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    s = db.query(CourseSlide).join(Course).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slide not found")
    s.title = body.title
    s.content = body.content or ""
    s.media_url = body.media_url
    if body.slide_type in SlideType.__members__:
        s.slide_type = SlideType(body.slide_type)
    if body.order_index is not None:
        s.order_index = body.order_index
    s.is_required = body.is_required
    db.commit()
    db.refresh(s)
    return SlideOut(
        id=s.id, title=s.title, content=s.content or "",
        slide_type=s.slide_type.value, media_url=s.media_url,
        order_index=s.order_index, is_required=s.is_required,
    )


@router.delete("/{course_id}/slides/{slide_id}")
def delete_slide(course_id: int, slide_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    s = db.query(CourseSlide).join(Course).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slide not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ── Enrollment & completion ────────────────────────────────────────
@router.post("/{course_id}/enroll")
def enroll(course_id: int, db: Session = Depends(get_db),
           current: CurrentUser = Depends(get_current_user)):
    from services.gamification_service import (
        XP_FIRST_ENROLLMENT, GamificationService,
    )
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
        Course.status == CourseStatus.PUBLISHED,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found or not published")
    if c.price_cents > 0:
        # Caller should hit /api/billing/subscribe instead
        from models import Subscription, SubscriptionStatus
        sub = db.query(Subscription).filter(
            Subscription.user_id == current.id, Subscription.course_id == course_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).first()
        if not sub:
            raise HTTPException(status_code=402, detail="Subscription required for paid course")
    existing = db.query(Enrollment).filter(
        Enrollment.user_id == current.id, Enrollment.course_id == course_id,
    ).first()
    if existing:
        return {"ok": True, "enrollment_id": existing.id, "already": True}
    e = Enrollment(user_id=current.id, course_id=course_id)
    db.add(e)
    db.flush()
    gam = GamificationService(db)
    gam.award_xp(current.id, XP_FIRST_ENROLLMENT)
    enroll_count = db.query(Enrollment).filter(Enrollment.user_id == current.id).count()
    if enroll_count == 1:
        gam.award_badge(current.id, "FIRST_ENROLLMENT")
    db.commit()
    return {"ok": True, "enrollment_id": e.id, "already": False}


@router.post("/{course_id}/complete")
def complete_course(course_id: int, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    from datetime import datetime, timezone

    from models import Certificate
    from services.gamification_service import (
        XP_COURSE_COMPLETE, GamificationService,
    )

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
    if not cert:
        db.add(Certificate(user_id=current.id, course_id=course_id, type="COURSE_COMPLETION"))

    if already:
        db.commit()
        return {"ok": True, "xp_earned": 0, "badges_earned": [], "already_completed": True}

    gam = GamificationService(db)
    gam.award_xp(current.id, XP_COURSE_COMPLETE)
    gam.notify(current.id, "COURSE_COMPLETE",
               f"🎓 Completed: {c.title}",
               f"You earned {XP_COURSE_COMPLETE} XP and a certificate!", "/certificates")
    completed = db.query(Enrollment).filter(
        Enrollment.user_id == current.id, Enrollment.status == EnrollmentStatus.COMPLETED,
    ).count()
    badges = []
    if completed == 1 and gam.award_badge(current.id, "FIRST_COURSE"):
        badges.append("FIRST_COURSE")
    if completed >= 5 and gam.award_badge(current.id, "COURSE_MASTER"):
        badges.append("COURSE_MASTER")
    db.commit()
    return {"ok": True, "xp_earned": XP_COURSE_COMPLETE, "badges_earned": badges}
