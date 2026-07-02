"""Mind maps (Iter 27b) + PPTX export (Iter 27c) — both staff-only.

Two related "course-shape" outputs in one router:
- POST /api/authoring/mindmap/{course_id}    — LLM-generated node/edge JSON
- GET  /api/authoring/pptx/{course_id}        — python-pptx download
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_staff
from core.database import get_db
from models import Course, CourseSlide
from services import ai_budget_service, audit_service, mindmap_service, pptx_export_service

logger = logging.getLogger("ifpi.authoring.extras")

router = APIRouter(prefix="/api/authoring", tags=["AI Authoring"])


@router.post("/mindmap/{course_id}")
async def generate_mindmap(
    course_id: int,
    max_topics: int = 6,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    ai_budget_service.check_budget(db, current.organization_id,
                                    estimated_cost_cents=2)

    slides = db.query(CourseSlide).filter(
        CourseSlide.course_id == course.id
    ).order_by(CourseSlide.order_index.asc()).all()

    slide_dicts = [{"title": s.title, "content": s.content or ""} for s in slides]
    graph = await mindmap_service.generate_mindmap(
        course_title=course.title, slides=slide_dicts, max_topics=max_topics,
    )

    ai_budget_service.record_spend(
        db, organization_id=current.organization_id, user_id=current.id,
        provider="openai", model="gpt-4o-mini", cost_cents=1,
        input_tokens=sum(len(s["content"]) // 4 for s in slide_dicts),
        output_tokens=len(str(graph)) // 4,
    )
    audit_service.record(
        db, current, "AI_MINDMAP_GENERATED",
        target_type="course", target_id=str(course.id),
        metadata={"topic_count": len(graph.get("topics") or [])},
    )
    db.commit()

    return {"course_id": course.id, "course_title": course.title, **graph}


@router.get("/pptx/{course_id}")
def export_course_pptx(
    course_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    slides = db.query(CourseSlide).filter(
        CourseSlide.course_id == course.id
    ).order_by(CourseSlide.order_index.asc()).all()

    slide_dicts = [{
        "title": s.title,
        "content": s.content or "",
        "slide_type": s.slide_type.value if hasattr(s.slide_type, "value") else str(s.slide_type),
        "media_url": s.media_url,
    } for s in slides]

    data = pptx_export_service.build_pptx(
        course_title=course.title,
        description=course.description or "",
        slides=slide_dicts,
    )

    audit_service.record(
        db, current, "COURSE_PPTX_EXPORTED",
        target_type="course", target_id=str(course.id),
        metadata={"slide_count": len(slide_dicts), "bytes": len(data)},
    )
    db.commit()

    # Slugify for a friendly filename
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in course.title)[:60].strip() or "course"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pptx"'},
    )


# ─── Mind map layout persistence (Iter 28) ───────────────────────────
class MindMapLayoutIn(BaseModel):
    """React-flow positions per node id. We also snapshot the labelled
    graph so a re-open shows the exact structure the admin last saved
    without re-running the LLM."""
    graph: dict = Field(..., description="{root, topics} shape from the LLM")
    positions: dict = Field(..., description="{node_id: {x, y}}")
    thumbnail_svg: Optional[str] = Field(
        default=None, max_length=200_000,
        description="Base64-encoded SVG snapshot for course card preview (Iter 30b)",
    )


@router.get("/mindmap/{course_id}/layout")
def load_mindmap_layout(
    course_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    meta = course.metadata_json or {}
    saved = meta.get("mindmap_layout")
    if not saved:
        return {"has_saved": False}
    return {"has_saved": True, **saved}


@router.put("/mindmap/{course_id}/layout")
def save_mindmap_layout(
    course_id: int, body: MindMapLayoutIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    from datetime import datetime, timezone
    meta = dict(course.metadata_json or {})
    meta["mindmap_layout"] = {
        "graph": body.graph,
        "positions": body.positions,
        "saved_by_id": current.id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    # Persist optional SVG thumbnail so course cards can render a small
    # preview without re-running the LLM or reactflow (Iter 30b).
    if body.thumbnail_svg:
        meta["mindmap_thumbnail_svg"] = body.thumbnail_svg
    course.metadata_json = meta
    audit_service.record(
        db, current, "MINDMAP_LAYOUT_SAVED",
        target_type="course", target_id=str(course.id),
        metadata={"node_count": len(body.positions),
                  "has_thumbnail": bool(body.thumbnail_svg)},
    )
    db.commit()
    return {"ok": True, "saved_at": meta["mindmap_layout"]["saved_at"]}


@router.delete("/mindmap/{course_id}/layout")
def clear_mindmap_layout(
    course_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    meta = dict(course.metadata_json or {})
    meta.pop("mindmap_layout", None)
    meta.pop("mindmap_thumbnail_svg", None)
    course.metadata_json = meta
    db.commit()
    return {"ok": True}
