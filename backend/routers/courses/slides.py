"""Slide CRUD, reordering, versioning and rich-text sanitize helper."""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import (
    Course, CourseSlide, SlideType,
)
from schemas import (
    SlideIn, SlideOut,
)
from routers.courses.common import (  # noqa: F401
    _can_manage, _detail, _summary, router,
)
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
        media_opacity=max(20, min(int(body.media_opacity), 100)) if body.media_opacity is not None else 100,
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
        media_opacity=s.media_opacity if s.media_opacity is not None else 100,
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
    if body.media_opacity is not None:
        s.media_opacity = max(20, min(int(body.media_opacity), 100))
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
        media_opacity=s.media_opacity if s.media_opacity is not None else 100,
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
    from models.ai import Flashcard
    from models.engagement import SlideView
    from models.learning import ScormPackage, SlideComment
    db.query(SlideView).filter(SlideView.slide_id == slide_id).delete(synchronize_session=False)
    db.query(SlideComment).filter(SlideComment.slide_id == slide_id).delete(synchronize_session=False)
    db.query(Flashcard).filter(Flashcard.slide_id == slide_id).update({"slide_id": None}, synchronize_session=False)
    db.query(ScormPackage).filter(ScormPackage.slide_id == slide_id).update({"slide_id": None}, synchronize_session=False)
    db.delete(s)
    db.commit()
    return {"ok": True}


