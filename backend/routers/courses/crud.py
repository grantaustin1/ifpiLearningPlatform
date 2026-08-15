"""Course CRUD, lifecycle (publish/archive/delete) and duplication."""
from __future__ import annotations

from typing import List

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import (
    Course, CourseStatus,
)
from schemas import (
    CourseCreate, CourseDetail, CourseSummary, CourseUpdate,
)
from routers.courses.common import (  # noqa: F401
    _can_manage, _detail, _summary, router,
)
from services.course_lifecycle_service import CourseLifecycleService


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


@router.post("/{course_id}/toggle-featured")
def toggle_featured(course_id: int, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Flip the marketplace 'Featured' flag on a course (Iter 42)."""
    return CourseLifecycleService(db).toggle_featured(current, course_id)


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    return CourseLifecycleService(db).delete(current, course_id)


@router.post("/{course_id}/publish")
def publish_course(course_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Explicit publish action — course must have at least one slide."""
    return CourseLifecycleService(db).publish(current, course_id)


@router.post("/{course_id}/archive")
def archive_course(course_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Safe alternative to deletion — blocked while learners are busy."""
    return CourseLifecycleService(db).archive(current, course_id)


@router.post("/{course_id}/unarchive")
def unarchive_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Restore an archived course back to DRAFT (re-publish separately)."""
    return CourseLifecycleService(db).unarchive(current, course_id)


@router.post("/{course_id}/unpublish")
def unpublish_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    return CourseLifecycleService(db).unpublish(current, course_id)


@router.post("/{course_id}/duplicate")
def duplicate_course(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Deep-clone a course (with all slides) as a new DRAFT."""
    return CourseLifecycleService(db).duplicate(current, course_id)


