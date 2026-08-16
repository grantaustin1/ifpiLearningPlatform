"""Learner enrollment listing routes."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import (
    Enrollment,
)
from schemas import (
    EnrollmentOut,
)

logger = logging.getLogger(__name__)



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


