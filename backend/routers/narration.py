"""AI narration for course slides (Iter 26a).

Staff-only endpoints:
- POST /api/authoring/narration/generate — generate + attach narration to a
  slide. Body: `{slide_id, voice?: "nova", model?: "tts-1"}`. Uses the
  slide's `content` as the source text; strips HTML if present.
- DELETE /api/authoring/narration/{slide_id} — drop the cached narration
  so a future generate call remakes it (and re-charges).

Learner-side there is nothing new — the existing GET /api/courses/{id}
already returns each slide including `narration_url`, and the learner
player renders an <audio> element when it's set.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_staff
from core.database import get_db
from models import Course, CourseSlide
from services import ai_budget_service, tts_service

logger = logging.getLogger("ifpi.narration")

router = APIRouter(prefix="/api/authoring/narration", tags=["AI Authoring"])


_TAG_RE = re.compile(r"<[^>]+>")


def _plain_text(html_or_text: str) -> str:
    """Strip HTML tags for TTS — course slides may store rich text."""
    if not html_or_text:
        return ""
    # Replace <br> and </p> with newlines so sentence breaks are preserved
    txt = re.sub(r"<br\s*/?>|</p>", " ", html_or_text, flags=re.I)
    txt = _TAG_RE.sub("", txt)
    # Collapse whitespace + decode common HTML entities
    txt = (txt.replace("&nbsp;", " ")
              .replace("&amp;", "&")
              .replace("&lt;", "<")
              .replace("&gt;", ">")
              .replace("&quot;", '"'))
    return re.sub(r"\s+", " ", txt).strip()


class NarrationIn(BaseModel):
    slide_id: int
    voice: str = Field(default="nova", max_length=20)
    model: str = Field(default="tts-1", max_length=20)
    override_text: Optional[str] = Field(default=None, max_length=25000)


@router.post("/generate")
async def generate_narration(
    body: NarrationIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    slide = (
        db.query(CourseSlide)
        .join(Course, CourseSlide.course_id == Course.id)
        .filter(
            CourseSlide.id == body.slide_id,
            Course.organization_id == current.organization_id,
        ).first()
    )
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")

    text = body.override_text or _plain_text(slide.content or "")
    if len(text) < 20:
        raise HTTPException(
            status_code=400,
            detail="Slide has too little text to narrate (need at least 20 chars)",
        )

    # Budget pre-flight — narration billed per 1K chars
    est = tts_service.estimated_cost_cents(text, model=body.model)
    ai_budget_service.check_budget(db, current.organization_id,
                                    estimated_cost_cents=est)

    result = await tts_service.generate_narration(
        text=text, model=body.model, voice=body.voice,
        org_id=current.organization_id, slide_id=slide.id,
    )

    slide.narration_url = result["url"]
    slide.narration_voice = result["voice"]

    # Record spend + audit
    ai_budget_service.record_spend(
        db, organization_id=current.organization_id, user_id=current.id,
        provider="openai", model=body.model, cost_cents=est,
        input_tokens=len(text) // 4, output_tokens=0,
    )
    from services import audit_service
    audit_service.record(
        db, current, "AI_NARRATION_GENERATED",
        target_type="slide", target_id=str(slide.id),
        metadata={"voice": body.voice, "model": body.model,
                  "chars": len(text), "size_bytes": result["size_bytes"]},
    )
    db.commit()
    db.refresh(slide)

    return {
        "slide_id": slide.id,
        "narration_url": slide.narration_url,
        "voice": slide.narration_voice,
        "model": body.model,
        "size_bytes": result["size_bytes"],
        "chunk_count": result["chunk_count"],
        "cost_cents": est,
    }


@router.delete("/{slide_id}")
def clear_narration(
    slide_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    slide = (
        db.query(CourseSlide)
        .join(Course, CourseSlide.course_id == Course.id)
        .filter(
            CourseSlide.id == slide_id,
            Course.organization_id == current.organization_id,
        ).first()
    )
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    slide.narration_url = None
    slide.narration_voice = None
    db.commit()
    return {"ok": True, "slide_id": slide_id}
