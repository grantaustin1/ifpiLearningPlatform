"""Shared router object + helpers for the courses package."""
from __future__ import annotations


from fastapi import APIRouter

from auth.dependencies import CurrentUser, can_manage_content
from models import (
    Course,
)
from schemas import (
    CourseDetail, CourseSummary, SlideOut,
)

router = APIRouter(prefix="/api/courses", tags=["Courses"])


def _can_manage(user: CurrentUser) -> bool:
    return can_manage_content(user)


def _summary(c: Course, slide_count: int | None = None,
             enrollment_count: int | None = None) -> CourseSummary:
    meta = c.metadata_json or {}
    return CourseSummary(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, cover_image=c.cover_image,
        is_featured=bool(c.is_featured), status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency,
        slide_count=len(c.slides) if slide_count is None else slide_count,
        enrollment_count=(len(c.enrollments) if enrollment_count is None
                          else enrollment_count),
        created_at=c.created_at,
        mindmap_thumbnail_svg=meta.get("mindmap_thumbnail_svg"),
        created_by_id=c.created_by_id,
    )


def _detail(c: Course, exam=None, exam_passed: bool = False,
            enrollment_count: int | None = None) -> CourseDetail:
    meta = c.metadata_json or {}
    return CourseDetail(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, cover_image=c.cover_image,
        is_featured=bool(c.is_featured), status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, passing_score=c.passing_score,
        slide_count=len(c.slides),
        enrollment_count=(len(c.enrollments) if enrollment_count is None
                          else enrollment_count),
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
        media_opacity=s.media_opacity if s.media_opacity is not None else 100,
        ) for s in c.slides],
    )


