from __future__ import annotations

from models import Course
from schemas import CourseSummary


def _can_manage(user) -> bool:
    from core.role_registry import INSTRUCTOR_ROLES
    return user.has_any_role(INSTRUCTOR_ROLES)


def _summary(c: Course) -> CourseSummary:
    meta = c.metadata_json or {}
    return CourseSummary(
        id=c.id, title=c.title, description=c.description, category=c.category,
        cover_color=c.cover_color, status=c.status.value,
        duration_minutes=c.duration_minutes, price_cents=c.price_cents,
        currency=c.currency, slide_count=len(c.slides),
        enrollment_count=len(c.enrollments), created_at=c.created_at,
        mindmap_thumbnail_svg=meta.get("mindmap_thumbnail_svg"),
    )
