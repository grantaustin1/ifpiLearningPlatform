"""Enrollment, slide progress and course completion — thin HTTP layer.
Business logic lives in services/enrollment_service.py."""
from __future__ import annotations

from fastapi import Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from routers.courses.common import router
from services.db_locks import retry_on_deadlock
from services.enrollment_service import EnrollmentService


@router.post("/{course_id}/enroll")
@retry_on_deadlock()
def enroll(course_id: int, db: Session = Depends(get_db),
           current: CurrentUser = Depends(get_current_user)):
    return EnrollmentService(db).enroll(current, course_id)


class SlideProgressIn(BaseModel):
    slide_index: int


@router.post("/{course_id}/progress")
def save_slide_progress(course_id: int, body: SlideProgressIn,
                        db: Session = Depends(get_db),
                        current: CurrentUser = Depends(get_current_user)):
    """Remember the learner's position so they resume across devices."""
    return EnrollmentService(db).save_progress(current, course_id, body.slide_index)


@router.post("/{course_id}/complete")
@retry_on_deadlock()
def complete_course(course_id: int, request: Request, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    return EnrollmentService(db).complete(current, course_id, str(request.base_url))
