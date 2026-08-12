"""Course routes: CRUD + slide management. Role-gated at the API layer."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import ADMIN_ROLES, INSTRUCTOR_ROLES
from services.db_locks import retry_on_deadlock
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
    meta = c.metadata_json or {}
    return CourseSummary(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, cover_image=c.cover_image,
        is_featured=bool(c.is_featured), status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, slide_count=len(c.slides),
        enrollment_count=len(c.enrollments), created_at=c.created_at,
        mindmap_thumbnail_svg=meta.get("mindmap_thumbnail_svg"),
        created_by_id=c.created_by_id,
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
    courses = query.order_by(Course.display_order.asc(), Course.created_at.desc()).all()
    return [_summary(c) for c in courses]


@router.patch("/reorder")
def reorder_catalog(
    body: dict, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")),
):
    """Body: {"course_ids": [id1, id2, ...]} — sets display_order to the
    list index. Only courses in the caller's org are updated."""
    ids = body.get("course_ids") or []
    rows = db.query(Course).filter(
        Course.id.in_(ids),
        Course.organization_id == current.organization_id,
    ).all()
    by_id = {c.id: c for c in rows}
    for idx, cid in enumerate(ids):
        if cid in by_id:
            by_id[cid].display_order = idx
    db.commit()
    return {"ok": True, "updated": len(rows)}


@router.post("", response_model=CourseDetail)
def create_course(
    body: CourseCreate, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")),
):
    # Pre-flight duplicate check so we return 409 instead of a 500 from the
    # DB unique constraint (uq_courses_org_title, Iter 25b).
    dup = db.query(Course).filter(
        Course.organization_id == current.organization_id,
        Course.title == body.title,
    ).first()
    if dup:
        raise HTTPException(status_code=409,
                            detail=f'A course titled "{body.title}" already exists')
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


def _detail(c: Course, exam=None, exam_passed: bool = False) -> CourseDetail:
    meta = c.metadata_json or {}
    return CourseDetail(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, cover_image=c.cover_image,
        is_featured=bool(c.is_featured), status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, passing_score=c.passing_score,
        slide_count=len(c.slides), enrollment_count=len(c.enrollments),
        created_at=c.created_at,
        mindmap_thumbnail_svg=meta.get("mindmap_thumbnail_svg"),
        exam_id=exam.id if exam else None,
        exam_title=exam.title if exam else None,
        exam_passed=exam_passed,
        slides=[SlideOut(
            id=s.id, title=s.title, content=s.content or "",
            slide_type=s.slide_type.value, media_url=s.media_url,
            order_index=s.order_index, is_required=s.is_required,
            narration_url=s.narration_url, narration_voice=s.narration_voice,
            image_position=s.image_position or "above",
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
    # Iter 49 — Exam gate metadata for the course player
    from models import Exam, ExamAttempt
    exam = db.query(Exam).filter(
        Exam.course_id == c.id, Exam.is_published.is_(True),
    ).first()
    exam_passed = False
    if exam:
        exam_passed = db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.user_id == current.id,
            ExamAttempt.passed.is_(True),
        ).first() is not None
    return _detail(c, exam=exam, exam_passed=exam_passed)


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


@router.post("/{course_id}/rating")
def rate_course(course_id: int, body: dict, db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    """Rate a course you have COMPLETED (1-5 stars, upsert). Iter 44."""
    from models import CourseRating
    rating = body.get("rating")
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise HTTPException(status_code=422, detail="rating must be an integer 1-5")
    enr = db.query(Enrollment).filter(
        Enrollment.course_id == course_id, Enrollment.user_id == current.id,
        Enrollment.completed_at.isnot(None),
    ).first()
    if not enr:
        raise HTTPException(status_code=403, detail="Complete the course before rating it")
    row = db.query(CourseRating).filter(
        CourseRating.course_id == course_id, CourseRating.user_id == current.id,
    ).first()
    if row:
        row.rating = rating
        if "comment" in body:
            row.comment = body.get("comment") or None
    else:
        db.add(CourseRating(course_id=course_id, user_id=current.id,
                            rating=rating, comment=body.get("comment") or None))
    db.commit()
    avg, count = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)) \
        .filter(CourseRating.course_id == course_id).one()
    return {"ok": True, "my_rating": rating,
            "avg_rating": round(float(avg), 1) if avg else None, "rating_count": count}


@router.get("/{course_id}/rating")
def get_course_rating(course_id: int, db: Session = Depends(get_db),
                      current: CurrentUser = Depends(get_current_user)):
    """Average + count + the caller's own rating for a course."""
    from models import CourseRating
    avg, count = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)) \
        .filter(CourseRating.course_id == course_id).one()
    mine = db.query(CourseRating).filter(
        CourseRating.course_id == course_id, CourseRating.user_id == current.id,
    ).first()
    return {"avg_rating": round(float(avg), 1) if avg else None,
            "rating_count": count,
            "my_rating": mine.rating if mine else None,
            "my_comment": mine.comment if mine else None}


@router.get("/{course_id}/reviews")
def list_course_reviews(course_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """All written reviews for a course (incl. hidden) — admin moderation view. Iter 47."""
    from models import CourseRating, User
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    rows = (db.query(CourseRating, User.name, User.email)
            .join(User, User.id == CourseRating.user_id)
            .filter(CourseRating.course_id == course_id,
                    CourseRating.comment.isnot(None), CourseRating.comment != "")
            .order_by(CourseRating.created_at.desc()).all())
    return [{
        "id": r.id, "rating": r.rating, "comment": r.comment,
        "hidden": r.hidden_at is not None,
        "reply_text": r.reply_text,
        "reply_at": r.reply_at.isoformat() if r.reply_at else None,
        "reviewer_name": name or email,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r, name, email in rows]


@router.post("/{course_id}/reviews/{rating_id}/reply")
def reply_to_review(course_id: int, rating_id: int, body: dict,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Post/update a public academy reply under a learner review.
    Empty string clears the reply. Iter 48."""
    from datetime import datetime, timezone
    from models import CourseRating
    reply = body.get("reply")
    if not isinstance(reply, str) or len(reply) > 1000:
        raise HTTPException(status_code=422, detail="reply must be a string of at most 1000 characters")
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    row = db.query(CourseRating).filter(
        CourseRating.id == rating_id, CourseRating.course_id == course_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    reply = reply.strip()
    row.reply_text = reply or None
    row.reply_at = datetime.now(timezone.utc) if reply else None
    db.commit()
    return {"ok": True, "reply_text": row.reply_text,
            "reply_at": row.reply_at.isoformat() if row.reply_at else None}


@router.post("/{course_id}/reviews/{rating_id}/toggle-hidden")
def toggle_review_hidden(course_id: int, rating_id: int, db: Session = Depends(get_db),
                         current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Hide/unhide a written review from the public course page. Iter 47."""
    from datetime import datetime, timezone
    from models import CourseRating
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    row = db.query(CourseRating).filter(
        CourseRating.id == rating_id, CourseRating.course_id == course_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    row.hidden_at = None if row.hidden_at else datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "hidden": row.hidden_at is not None}


@router.post("/{course_id}/toggle-featured")
def toggle_featured(course_id: int, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Flip the marketplace 'Featured' flag on a course (Iter 42)."""
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    c.is_featured = not bool(c.is_featured)
    db.commit()
    return {"id": c.id, "is_featured": c.is_featured}


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if "SUPER_ADMIN" not in current.roles and c.created_by_id != current.id:
        raise HTTPException(
            status_code=403,
            detail="Only the course owner or a super admin can delete this course")
    if c.status == CourseStatus.PUBLISHED:
        raise HTTPException(
            status_code=409,
            detail="Unpublish the course first, then delete it")
    # Iter 47 — clean up FK dependents so the delete never 500s.
    from models import (
        AITutorSession, Certificate, CoursePrerequisite, CourseRating,
        CourseView, Exam, Flashcard, LearningPathItem, ScormPackage,
        SlideComment, SlideVersion, SlideView, SourceDocument, Subscription,
        LiveSession,
    )
    slide_ids = [s.id for s in c.slides]
    if slide_ids:
        for model in (SlideComment, SlideView, SlideVersion):
            db.query(model).filter(model.slide_id.in_(slide_ids)) \
                .delete(synchronize_session=False)
        db.query(ScormPackage).filter(ScormPackage.slide_id.in_(slide_ids)) \
            .update({ScormPackage.slide_id: None}, synchronize_session=False)
    # Course-owned rows — hard delete alongside the course
    for model in (Flashcard, CourseRating, CourseView, LearningPathItem,
                  AITutorSession):
        db.query(model).filter(model.course_id == course_id) \
            .delete(synchronize_session=False)
    db.query(CoursePrerequisite).filter(
        (CoursePrerequisite.course_id == course_id)
        | (CoursePrerequisite.prerequisite_course_id == course_id)
    ).delete(synchronize_session=False)
    # Historical records — keep the row, detach the course reference
    for model in (Exam, Certificate, Subscription, SourceDocument,
                  LiveSession, ScormPackage):
        db.query(model).filter(model.course_id == course_id) \
            .update({model.course_id: None}, synchronize_session=False)
    db.delete(c)  # slides + enrollments cascade via ORM relationships
    from services import audit_service
    audit_service.record(db, current, "COURSE_DELETED",
                         target_type="course", target_id=course_id,
                         metadata={"title": c.title})
    db.commit()
    return {"ok": True}


@router.post("/{course_id}/publish")
def publish_course(course_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Explicit publish action with validation. Course must have at least
    one slide before it can be published."""
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if len(c.slides) == 0:
        raise HTTPException(status_code=400, detail="Add at least one slide before publishing")
    c.status = CourseStatus.PUBLISHED
    db.commit()
    return {"ok": True, "status": c.status.value, "course_id": c.id, "title": c.title}


@router.post("/{course_id}/archive")
def archive_course(course_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Safe alternative to deletion — hides the course from learners and the
    catalog, keeps everything restorable. Blocked while learners are busy."""
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if c.status == CourseStatus.ARCHIVED:
        return {"ok": True, "status": c.status.value, "course_id": c.id}
    busy = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.status == EnrollmentStatus.IN_PROGRESS,
    ).count()
    if busy:
        raise HTTPException(
            status_code=409,
            detail=f"{busy} learner{'s are' if busy != 1 else ' is'} still busy with this course")
    c.status = CourseStatus.ARCHIVED
    from services import audit_service
    audit_service.record(db, current, "COURSE_ARCHIVED",
                         target_type="course", target_id=course_id,
                         metadata={"title": c.title})
    db.commit()
    return {"ok": True, "status": c.status.value, "course_id": c.id, "title": c.title}


@router.post("/{course_id}/unarchive")
def unarchive_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Restore an archived course back to DRAFT (re-publish separately)."""
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if c.status != CourseStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Course is not archived")
    c.status = CourseStatus.DRAFT
    from services import audit_service
    audit_service.record(db, current, "COURSE_UNARCHIVED",
                         target_type="course", target_id=course_id,
                         metadata={"title": c.title})
    db.commit()
    return {"ok": True, "status": c.status.value, "course_id": c.id, "title": c.title}


@router.post("/{course_id}/unpublish")
def unpublish_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    c.status = CourseStatus.DRAFT
    db.commit()
    return {"ok": True, "status": c.status.value}


@router.post("/{course_id}/duplicate")
def duplicate_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Deep-clone a course (with all slides) as a new DRAFT. Optional template path:
    instructors can keep a master "template" course and duplicate it as a base
    for each new cohort."""
    src = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not src:
        raise HTTPException(status_code=404, detail="Course not found")
    new_course = Course(
        organization_id=src.organization_id,
        title=f"{src.title} (copy)",
        description=src.description, category=src.category,
        cover_color=src.cover_color, cover_image=src.cover_image,
        status=CourseStatus.DRAFT,
        passing_score=src.passing_score, duration_minutes=src.duration_minutes,
        price_cents=src.price_cents, currency=src.currency,
        created_by_id=current.id,
    )
    db.add(new_course)
    db.flush()
    for s in src.slides:
        db.add(CourseSlide(
            course_id=new_course.id, title=s.title, content=s.content,
            slide_type=s.slide_type, media_url=s.media_url,
            order_index=s.order_index, is_required=s.is_required,
        ))
    db.commit()
    db.refresh(new_course)
    return {
        "ok": True, "course_id": new_course.id, "title": new_course.title,
        "slides_copied": len(src.slides),
    }


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
        image_position=body.image_position if body.image_position in ("above", "beside", "behind") else "above",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return SlideOut(
        id=s.id, title=s.title, content=s.content or "",
        slide_type=s.slide_type.value, media_url=s.media_url,
        order_index=s.order_index, is_required=s.is_required,
        narration_url=s.narration_url, narration_voice=s.narration_voice,
        image_position=s.image_position or "above",
    )


@router.patch("/{course_id}/slides/reorder")
def reorder_slides_early(course_id: int, body: dict, db: Session = Depends(get_db),
                         current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Reorder slides. Declared BEFORE /slides/{slide_id} to avoid path collision."""
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    ids = body.get("slide_ids") or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="slide_ids must be a list")
    slides = {s.id: s for s in c.slides}
    # Two-pass update to satisfy the (course_id, order_index) UNIQUE
    # constraint (Iter 25b): first move every affected row into a negative
    # index (guaranteed non-colliding), then set the final positive index.
    for i, sid in enumerate(ids, start=1):
        if sid in slides:
            slides[sid].order_index = -i
    db.flush()
    for i, sid in enumerate(ids, start=1):
        if sid in slides:
            slides[sid].order_index = i
    db.commit()
    return {"ok": True, "count": len(ids)}


@router.patch("/{course_id}/slides/{slide_id}", response_model=SlideOut)
def update_slide(course_id: int, slide_id: int, body: SlideIn, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    s = db.query(CourseSlide).join(Course).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slide not found")
    # Iter 19 — snapshot the PREVIOUS state for rollback before mutating
    from services.versioning_service import snapshot_slide
    changed = (s.title != body.title or (s.content or "") != (body.content or "")
               or s.media_url != body.media_url
               or (body.slide_type in SlideType.__members__
                   and s.slide_type != SlideType(body.slide_type)))
    if changed:
        snapshot_slide(db, s, changed_by_id=current.id, change_summary="Pre-edit snapshot")
    s.title = body.title
    s.content = body.content or ""
    s.media_url = body.media_url
    if body.image_position in ("above", "beside", "behind"):
        s.image_position = body.image_position
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
        narration_url=s.narration_url, narration_voice=s.narration_voice,
        image_position=s.image_position or "above",
    )


# ── Iter 19: Slide versioning endpoints ───────────────────────────────
@router.get("/{course_id}/slides/{slide_id}/versions")
def list_slide_versions(course_id: int, slide_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles(
                            "INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from services.versioning_service import list_versions
    s = db.query(CourseSlide).join(Course).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slide not found")
    return {"items": list_versions(db, slide_id)}


@router.get("/{course_id}/slides/{slide_id}/versions/{version_number}")
def get_slide_version(course_id: int, slide_id: int, version_number: int,
                      db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles(
                          "INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from services.versioning_service import get_version
    s = db.query(CourseSlide).join(Course).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slide not found")
    v = get_version(db, slide_id, version_number)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return {
        "id": v.id, "version_number": v.version_number,
        "title": v.title, "content": v.content,
        "slide_type": v.slide_type, "media_url": v.media_url,
        "change_summary": v.change_summary,
        "changed_by_id": v.changed_by_id,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/{course_id}/slides/{slide_id}/versions/{version_number}/restore")
def restore_slide_version(course_id: int, slide_id: int, version_number: int,
                          db: Session = Depends(get_db),
                          current: CurrentUser = Depends(requires_roles(
                              "INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from services.versioning_service import get_version, restore_version
    s = db.query(CourseSlide).join(Course).filter(
        CourseSlide.id == slide_id, CourseSlide.course_id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slide not found")
    target = get_version(db, slide_id, version_number)
    if not target:
        raise HTTPException(status_code=404, detail="Version not found")
    restore_version(db, s, target, changed_by_id=current.id)
    db.commit()
    db.refresh(s)
    return {
        "ok": True, "restored_to_version": version_number,
        "slide": {"id": s.id, "title": s.title, "media_url": s.media_url,
                  "slide_type": s.slide_type.value if s.slide_type else None},
    }


# ── Iter 19: Rich-text editor helper (separate prefix to avoid colliding
# with `/api/courses/{course_id}` paths) ──────────────────────────────
richtext_router = APIRouter(prefix="/api/rich-text", tags=["Rich Text"])


@richtext_router.post("/sanitize")
def sanitize_html_payload(body: dict,
                          _current: CurrentUser = Depends(requires_roles(
                              "INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Server-side HTML sanitizer for the rich-text editor preview.
    Strips dangerous tags/attrs while preserving formatting + media tags.
    """
    from core.sanitizer import sanitize_course_html
    raw = body.get("html") or ""
    return {"sanitized": sanitize_course_html(raw), "input_length": len(raw)}


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
@retry_on_deadlock()
def enroll(course_id: int, db: Session = Depends(get_db),
           current: CurrentUser = Depends(get_current_user)):
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
    # Prerequisite check
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
        # Delegate to the single-question entitlement service.
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
        return {"ok": True, "enrollment_id": existing.id if existing else None, "already": True,
                "last_slide_index": (existing.last_slide_index if existing else 0) or 0}
    gam = GamificationService(db)
    gam.award_xp(current.id, XP_FIRST_ENROLLMENT)
    enroll_count = db.query(Enrollment).filter(Enrollment.user_id == current.id).count()
    if enroll_count == 1:
        gam.award_badge(current.id, "FIRST_ENROLLMENT")
    db.commit()
    return {"ok": True, "enrollment_id": e.id, "already": False, "last_slide_index": 0}


from pydantic import BaseModel


class SlideProgressIn(BaseModel):
    slide_index: int


@router.post("/{course_id}/progress")
def save_slide_progress(course_id: int, body: SlideProgressIn,
                        db: Session = Depends(get_db),
                        current: CurrentUser = Depends(get_current_user)):
    """Remember the learner's position so they resume across devices."""
    e = db.query(Enrollment).filter(
        Enrollment.user_id == current.id, Enrollment.course_id == course_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Not enrolled")
    total = db.query(CourseSlide).filter(CourseSlide.course_id == course_id).count()
    idx = max(0, min(body.slide_index, max(total - 1, 0)))
    e.last_slide_index = idx
    if total and e.status != EnrollmentStatus.COMPLETED:
        e.progress = max(e.progress or 0.0, round((idx + 1) / total * 100, 1))
    db.commit()
    return {"ok": True, "last_slide_index": idx, "progress": e.progress}


@router.post("/{course_id}/complete")
@retry_on_deadlock()
def complete_course(course_id: int, request: Request, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    from datetime import datetime, timezone

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
        cert = Certificate(user_id=current.id, course_id=course_id, type="COURSE_COMPLETION")
        db.add(cert)
        db.flush()

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

    # Email the cert PDF (stub mode persists to outbox)
    if cert_is_new:
        try:
            from models import User
            user = db.query(User).filter(User.id == current.id).first()
            org = db.query(Organization).filter(Organization.id == current.organization_id).first()
            base = str(request.base_url).rstrip("/")
            verify_url = f"{base}/verify/{cert.code}"
            pdf_bytes = render_certificate(
                recipient_name=user.name or user.email,
                course_title=c.title, certificate_code=cert.code,
                issued_at=cert.issued_at, verify_url=verify_url,
                organisation_name=org.name if org else "IFPI Learning",
                organisation_logo_url=org.logo_url if org else None,
                accent_color=(org.cert_accent_color or org.primary_color or "#6366f1") if org else "#6366f1",
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
    return {"ok": True, "xp_earned": XP_COURSE_COMPLETE, "badges_earned": badges}


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


# ── Prerequisite management ───────────────────────────────────────────
@router.get("/{course_id}/prerequisites")
def list_prerequisites(course_id: int, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    from models import CoursePrerequisite
    rows = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
    ).all()
    out = []
    for r in rows:
        pc = db.query(Course).filter(Course.id == r.prerequisite_course_id).first()
        if pc:
            out.append({"id": r.id, "course_id": pc.id, "title": pc.title, "status": pc.status.value})
    return out


@router.post("/{course_id}/prerequisites/{prereq_course_id}")
def add_prerequisite(course_id: int, prereq_course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from models import CoursePrerequisite
    if course_id == prereq_course_id:
        raise HTTPException(status_code=400, detail="Course can't be its own prerequisite")
    # Both courses must belong to this org
    for cid in (course_id, prereq_course_id):
        if not db.query(Course).filter(
            Course.id == cid, Course.organization_id == current.organization_id,
        ).first():
            raise HTTPException(status_code=404, detail=f"Course #{cid} not found")
    existing = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
        CoursePrerequisite.prerequisite_course_id == prereq_course_id,
    ).first()
    if existing:
        return {"ok": True, "already": True}
    db.add(CoursePrerequisite(course_id=course_id, prerequisite_course_id=prereq_course_id))
    db.commit()
    return {"ok": True, "already": False}


@router.delete("/{course_id}/prerequisites/{prereq_course_id}")
def remove_prerequisite(course_id: int, prereq_course_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from models import CoursePrerequisite
    row = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
        CoursePrerequisite.prerequisite_course_id == prereq_course_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Prerequisite not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


# (Slide reorder route is declared earlier in this file, before the dynamic
# /slides/{slide_id} route — see line ~193 — to avoid FastAPI's prefix
# matching grabbing the static "reorder" path as a dynamic id.)
