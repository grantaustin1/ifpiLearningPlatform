from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import INSTRUCTOR_ROLES
from models import (
    Course, Enrollment, LearningPath, LearningPathEnrollment,
    LearningPathItem, LearningPathStatus,
)

from . import router
from ._schemas import PathCreate, PathDetail, PathItemIn, PathItemOut, PathSummary, PathUpdate


def _can_manage(user: CurrentUser) -> bool:
    return user.has_any_role(INSTRUCTOR_ROLES)


def _summary(p: LearningPath) -> PathSummary:
    return PathSummary(
        id=p.id, title=p.title, description=p.description,
        cover_color=p.cover_color, status=p.status.value,
        estimated_hours=p.estimated_hours, price_cents=p.price_cents,
        currency=p.currency, course_count=len(p.items),
        enrollment_count=len(p.enrollments),
    )


def _detail(p: LearningPath, user_id: int) -> PathDetail:
    items = [PathItemOut(
        id=i.id, course_id=i.course_id, course_title=i.course.title,
        course_status=i.course.status.value, order_index=i.order_index,
        is_required=i.is_required,
    ) for i in p.items]
    # Compute progress for this user
    enrollment_row = next((e for e in p.enrollments if e.user_id == user_id), None)
    return PathDetail(
        **_summary(p).model_dump(),
        items=items,
        user_progress=enrollment_row.progress if enrollment_row else 0.0,
        user_status=enrollment_row.status.value if enrollment_row else None,
    )


@router.get("", response_model=List[PathSummary])
def list_paths(db: Session = Depends(get_db),
               current: CurrentUser = Depends(get_current_user)) -> list:
    q = db.query(LearningPath).filter(LearningPath.organization_id == current.organization_id)
    if not _can_manage(current):
        q = q.filter(LearningPath.status == LearningPathStatus.PUBLISHED)
    return [_summary(p) for p in q.order_by(LearningPath.created_at.desc()).all()]


@router.post("", response_model=PathDetail)
def create_path(body: PathCreate, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> PathDetail:
    p = LearningPath(
        organization_id=current.organization_id, title=body.title,
        description=body.description, cover_color=body.cover_color,
        estimated_hours=body.estimated_hours, price_cents=body.price_cents,
        currency=body.currency, created_by_id=current.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _detail(p, current.id)


@router.get("/{path_id}", response_model=PathDetail)
def get_path(path_id: int, db: Session = Depends(get_db),
             current: CurrentUser = Depends(get_current_user)) -> PathDetail:
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Learning path not found")
    if p.status != LearningPathStatus.PUBLISHED and not _can_manage(current):
        raise HTTPException(status_code=404, detail="Learning path not found")
    return _detail(p, current.id)


@router.patch("/{path_id}", response_model=PathDetail)
def update_path(path_id: int, body: PathUpdate, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> PathDetail:
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Learning path not found")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] in LearningPathStatus.__members__:
        p.status = LearningPathStatus(data.pop("status"))
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _detail(p, current.id)


@router.delete("/{path_id}")
def delete_path(path_id: int, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Learning path not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{path_id}/items", response_model=PathItemOut)
def add_item(path_id: int, body: PathItemIn, db: Session = Depends(get_db),
             current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> PathItemOut:
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Learning path not found")
    course = db.query(Course).filter(
        Course.id == body.course_id, Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    existing = db.query(LearningPathItem).filter(
        LearningPathItem.path_id == path_id,
        LearningPathItem.course_id == body.course_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Course already in this path")
    order = body.order_index if body.order_index is not None else (len(p.items) + 1)
    item = LearningPathItem(
        path_id=path_id, course_id=body.course_id,
        order_index=order, is_required=body.is_required,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return PathItemOut(
        id=item.id, course_id=item.course_id, course_title=course.title,
        course_status=course.status.value, order_index=item.order_index,
        is_required=item.is_required,
    )


@router.delete("/{path_id}/items/{course_id}")
def remove_item(path_id: int, course_id: int, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> dict:
    item = db.query(LearningPathItem).join(LearningPath).filter(
        LearningPathItem.path_id == path_id,
        LearningPathItem.course_id == course_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/{path_id}/enroll")
def enroll_in_path(path_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)) -> dict:
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
        LearningPath.status == LearningPathStatus.PUBLISHED,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Learning path not found")
    existing = db.query(LearningPathEnrollment).filter(
        LearningPathEnrollment.user_id == current.id,
        LearningPathEnrollment.path_id == path_id,
    ).first()
    if existing:
        return {"ok": True, "already": True}
    db.add(LearningPathEnrollment(user_id=current.id, path_id=path_id))
    # Also enrol them in each of the path's courses (idempotent)
    for it in p.items:
        ex = db.query(Enrollment).filter(
            Enrollment.user_id == current.id, Enrollment.course_id == it.course_id,
        ).first()
        if not ex:
            db.add(Enrollment(user_id=current.id, course_id=it.course_id))
    db.commit()
    return {"ok": True, "already": False, "courses_enrolled": len(p.items)}


@router.post("/{path_id}/publish")
def publish_path(path_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))) -> dict:
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Learning path not found")
    if len(p.items) == 0:
        raise HTTPException(status_code=400, detail="Add at least one course before publishing")
    p.status = LearningPathStatus.PUBLISHED
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "status": p.status.value}
