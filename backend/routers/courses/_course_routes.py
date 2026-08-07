from __future__ import annotations

from typing import List

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import (
    AITutorSession,
    Certificate,
    Course,
    CoursePrerequisite,
    CourseRating,
    CourseStatus,
    CourseView,
    Exam,
    Flashcard,
    LearningPathItem,
    LiveSession,
    ScormPackage,
    SlideComment,
    SlideVersion,
    SlideView,
    SourceDocument,
    Subscription,
)
from schemas import CourseCreate, CourseDetail, CourseSummary, CourseUpdate, SlideOut

from . import router
from ._helpers import _can_manage, _summary


def _detail(c: Course) -> CourseDetail:
    meta = c.metadata_json or {}
    return CourseDetail(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, passing_score=c.passing_score,
        slide_count=len(c.slides), enrollment_count=len(c.enrollments),
        created_at=c.created_at,
        mindmap_thumbnail_svg=meta.get("mindmap_thumbnail_svg"),
        slides=[SlideOut(
            id=s.id, title=s.title, content=s.content or "",
            slide_type=s.slide_type.value, media_url=s.media_url,
            order_index=s.order_index, is_required=s.is_required,
            narration_url=s.narration_url, narration_voice=s.narration_voice,
        ) for s in c.slides],
    )


@router.get("", response_model=List[CourseSummary])
def list_courses(
    q: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list:
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
) -> dict:
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
) -> CourseDetail:
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


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, db: Session = Depends(get_db),
               current: CurrentUser = Depends(get_current_user)) -> CourseDetail:
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
                  current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> CourseDetail:
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
                  current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    # Clean up FK dependents so delete does not fail when slide activity,
    # comments, reviews, or other attached records exist.
    slide_ids = [s.id for s in c.slides]
    if slide_ids:
        for model in (SlideComment, SlideView, SlideVersion):
            db.query(model).filter(model.slide_id.in_(slide_ids)).delete(
                synchronize_session=False,
            )
        db.query(ScormPackage).filter(ScormPackage.slide_id.in_(slide_ids)).update(
            {ScormPackage.slide_id: None},
            synchronize_session=False,
        )
    for model in (Flashcard, CourseRating, CourseView, LearningPathItem,
                  AITutorSession):
        db.query(model).filter(model.course_id == course_id).delete(
            synchronize_session=False,
        )
    db.query(CoursePrerequisite).filter(
        (CoursePrerequisite.course_id == course_id)
        | (CoursePrerequisite.prerequisite_course_id == course_id)
    ).delete(synchronize_session=False)
    for model in (Exam, Certificate, Subscription, SourceDocument,
                  LiveSession, ScormPackage):
        db.query(model).filter(model.course_id == course_id).update(
            {model.course_id: None},
            synchronize_session=False,
        )
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/{course_id}/publish")
def publish_course(course_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> dict:
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


@router.post("/{course_id}/unpublish")
def unpublish_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> dict:
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
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> dict:
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
        from models import CourseSlide
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
