"""Slide content versioning (Iter 19).

Whenever a slide is updated (title / content / media_url / slide_type),
we append a `SlideVersion` row capturing the *previous* state. The current
state always lives in `course_slides`. Restoring a version = updating the
slide back to that snapshot AND appending a new version recording the
restore.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import CourseSlide, SlideVersion

logger = logging.getLogger("ifpi.versioning")


def _next_version_number(db: Session, slide_id: int) -> int:
    last = (
        db.query(SlideVersion)
        .filter(SlideVersion.slide_id == slide_id)
        .order_by(SlideVersion.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


def snapshot_slide(
    db: Session, slide: CourseSlide, *,
    changed_by_id: Optional[int] = None,
    change_summary: Optional[str] = None,
) -> SlideVersion:
    """Append a SlideVersion row for the current state of `slide`. Caller
    is responsible for db.commit().
    """
    ver = SlideVersion(
        slide_id=slide.id,
        version_number=_next_version_number(db, slide.id),
        title=slide.title or "",
        content=slide.content,
        slide_type=slide.slide_type.value if slide.slide_type else None,
        media_url=slide.media_url,
        changed_by_id=changed_by_id,
        change_summary=(change_summary or "")[:200] or None,
    )
    db.add(ver)
    db.flush()
    return ver


def list_versions(db: Session, slide_id: int) -> list[dict]:
    rows = (
        db.query(SlideVersion)
        .filter(SlideVersion.slide_id == slide_id)
        .order_by(SlideVersion.version_number.desc())
        .all()
    )
    return [
        {
            "id": v.id, "version_number": v.version_number,
            "title": v.title, "slide_type": v.slide_type,
            "media_url": v.media_url,
            "change_summary": v.change_summary,
            "changed_by_id": v.changed_by_id,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in rows
    ]


def get_version(db: Session, slide_id: int, version_number: int) -> Optional[SlideVersion]:
    return (
        db.query(SlideVersion)
        .filter(
            SlideVersion.slide_id == slide_id,
            SlideVersion.version_number == version_number,
        )
        .first()
    )


def restore_version(
    db: Session, slide: CourseSlide, target: SlideVersion, *,
    changed_by_id: Optional[int] = None,
) -> CourseSlide:
    """Update `slide` to match `target`'s snapshot and record the restore as
    a new SlideVersion. Caller commits.
    """
    # First — snapshot the CURRENT state so the restore itself is undo-able.
    snapshot_slide(
        db, slide, changed_by_id=changed_by_id,
        change_summary=f"Pre-restore snapshot (restoring to v{target.version_number})",
    )
    # Apply the target snapshot
    slide.title = target.title
    slide.content = target.content
    slide.media_url = target.media_url
    if target.slide_type:
        # slide_type is stored as enum on the live row — coerce
        from models import SlideType
        try:
            slide.slide_type = SlideType(target.slide_type)
        except ValueError:
            pass  # leave as-is
    db.flush()
    # Append a new version recording the restored state
    snapshot_slide(
        db, slide, changed_by_id=changed_by_id,
        change_summary=f"Restored from v{target.version_number}",
    )
    return slide
