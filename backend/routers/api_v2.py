"""API v2 — unified response envelope for external integrators.

Every response: {"data": ..., "meta": {...}}. Errors keep the global
{"error": {code, message, correlation_id}} envelope. v1 endpoints are
unchanged — the frontend stays on v1; v2 exists for third-party consumers
and future SDK generation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db

v2_router = APIRouter(prefix="/api/v2", tags=["API v2"])


def _envelope(data, **meta):
    return {"data": data, "meta": meta or {}}


@v2_router.get("/health", summary="Service health (enveloped)")
def v2_health():
    return _envelope({"status": "ok"}, version="v2")


@v2_router.get("/courses", summary="List courses visible to the caller")
def v2_courses(db: Session = Depends(get_db),
               current: CurrentUser = Depends(get_current_user)):
    from routers.courses.crud import list_courses
    items = list_courses(q=None, category=None, db=db, current=current)
    data = [i.model_dump() if hasattr(i, "model_dump") else i for i in items]
    return _envelope(data, count=len(data))


@v2_router.get("/courses/{course_id}", summary="Course detail with slides")
def v2_course_detail(course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(get_current_user)):
    from routers.courses.crud import get_course
    d = get_course(course_id=course_id, db=db, current=current)
    return _envelope(d.model_dump() if hasattr(d, "model_dump") else d)


@v2_router.get("/enrollments", summary="Caller's enrollments with progress")
def v2_enrollments(db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)):
    from models import Course, Enrollment
    rows = db.query(Enrollment, Course).join(
        Course, Course.id == Enrollment.course_id,
    ).filter(Enrollment.user_id == current.id).all()
    data = [{
        "enrollment_id": e.id, "course_id": c.id, "course_title": c.title,
        "status": e.status.value, "progress": e.progress,
        "last_slide_index": e.last_slide_index or 0,
        "enrolled_at": e.enrolled_at, "completed_at": e.completed_at,
    } for e, c in rows]
    return _envelope(data, count=len(data))


@v2_router.get("/catalog", summary="Public course catalog (enveloped)")
def v2_catalog(page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
               db: Session = Depends(get_db)):
    from routers.catalog import catalog
    raw = catalog(q=None, category=None, org=None, featured=False,
                  sort="newest", page=page, page_size=page_size, db=db)
    return _envelope(raw["courses"], total=raw["total"], page=raw["page"],
                     page_size=raw["page_size"], categories=raw["categories"])
