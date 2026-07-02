"""Sora 2 video overviews (Iter 26b) + Nano Banana infographics (Iter 27a).

Two related but distinct patterns in one module:

  ┌ /api/authoring/video/generate  (Sora 2 — takes 2-5 min, ASYNC via AIJob)
  │ /api/authoring/video/{job_id}   (poll)
  │ /api/authoring/video/history    (list recent jobs)
  │
  └ /api/authoring/visuals/generate (Nano Banana — sync, ~10s)
    /api/authoring/visuals/{slide_id} DELETE (clear cached image)

Video jobs persist their result on the target slide (slide.media_url +
slide_type=VIDEO). Visuals persist to slide.media_url with slide_type=IMAGE.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_staff
from core.database import SessionLocal, get_db
from models import AIJob, Course, CourseSlide, SlideType
from services import ai_budget_service, video_service, visuals_service, audit_service
from services.background_worker import submit_long_job

logger = logging.getLogger("ifpi.authoring.media")

router = APIRouter(prefix="/api/authoring", tags=["AI Authoring"])


# ─── Sora 2 video overview (async) ──────────────────────────────────
class VideoStartIn(BaseModel):
    prompt: str = Field(min_length=8, max_length=2000)
    slide_id: Optional[int] = None
    model: str = "sora-2"
    size: str = "1280x720"
    duration: int = 4


class VideoPreviewIn(BaseModel):
    model: str = "sora-2"
    duration: int = 4


@router.post("/video/preview")
def video_cost_preview(
    body: VideoPreviewIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Show the estimated cost + remaining budget BEFORE firing a Sora
    render. Frontend shows this in the spend-preview modal."""
    video_service.validate_params(body.model, "1280x720", body.duration)
    est = video_service.estimated_cost_cents(body.model, body.duration)
    status = ai_budget_service.get_budget_status(db, current.organization_id)
    return {
        "estimated_cost_cents": est,
        "budget": status,
        "will_exceed_budget": status["remaining_cents"] is not None
            and status["remaining_cents"] < est,
    }


def _run_video_job(job_id: int, org_id: int, user_id: int,
                    prompt: str, model: str, size: str, duration: int,
                    slide_id: Optional[int]) -> None:
    """Runs on a background thread (FastAPI BackgroundTasks). Blocks 2-5 min
    inside the Sora call. On completion, attaches the video to the slide
    (if provided) and marks the job COMPLETED."""
    db = SessionLocal()
    try:
        job = db.query(AIJob).filter(AIJob.id == job_id).first()
        if not job:
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            result = video_service.generate_video_sync(
                prompt=prompt, model=model, size=size, duration=duration,
                org_id=org_id,
            )
        except Exception as e:   # noqa: BLE001
            logger.exception("Sora job crashed: %s", e)
            job.status = "FAILED"
            job.error_log = f"{type(e).__name__}: {e}"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Persist cost
        cost = video_service.estimated_cost_cents(model, duration)
        try:
            ai_budget_service.record_spend(
                db, organization_id=org_id, user_id=user_id, job_id=job_id,
                provider="openai", model=model, cost_cents=cost,
            )
        except Exception:   # noqa: BLE001
            logger.exception("Failed to record sora spend")

        # Optionally attach to slide
        if slide_id:
            slide = db.query(CourseSlide).join(Course).filter(
                CourseSlide.id == slide_id,
                Course.organization_id == org_id,
            ).first()
            if slide:
                slide.media_url = result["url"]
                slide.slide_type = SlideType.VIDEO

        job.status = "COMPLETED"
        job.output_json = {
            "video_url": result["url"], "storage_key": result["storage_key"],
            "size_bytes": result["size_bytes"], "model": result["model"],
            "size": result["size"], "duration": result["duration"],
            "slide_id": slide_id,
        }
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:   # noqa: BLE001
        logger.exception("Sora job runner unhandled: %s", e)
    finally:
        db.close()


@router.post("/video/generate", status_code=202)
def start_video_generation(
    body: VideoStartIn,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Kick off a Sora 2 job. Returns 202 with the AIJob id — poll
    /video/{job_id} to check progress."""
    video_service.validate_params(body.model, body.size, body.duration)
    est = video_service.estimated_cost_cents(body.model, body.duration)
    ai_budget_service.check_budget(db, current.organization_id,
                                    estimated_cost_cents=est)

    if body.slide_id:
        slide = db.query(CourseSlide).join(Course).filter(
            CourseSlide.id == body.slide_id,
            Course.organization_id == current.organization_id,
        ).first()
        if not slide:
            raise HTTPException(status_code=404, detail="Slide not found")

    job = AIJob(
        organization_id=current.organization_id,
        created_by_id=current.id, job_type="SORA_VIDEO",
        status="PENDING",
        input_json={
            "prompt": body.prompt, "model": body.model,
            "size": body.size, "duration": body.duration,
            "slide_id": body.slide_id,
        },
    )
    db.add(job); db.commit(); db.refresh(job)

    audit_service.record(
        db, current, "AI_VIDEO_JOB_STARTED",
        target_type="ai_job", target_id=str(job.id),
        metadata={"prompt_len": len(body.prompt), "model": body.model,
                  "duration": body.duration, "est_cost_cents": est},
    )
    db.commit()

    # Off-load to the dedicated long-worker pool so FastAPI's anyio pool
    # isn't saturated by 3-5 minute Sora renders (Iter 28 fix).
    submit_long_job(
        _run_video_job, job.id, current.organization_id, current.id,
        body.prompt, body.model, body.size, body.duration, body.slide_id,
    )
    _ = bg   # BackgroundTasks kept in signature for now (unused after the switch)
    return {
        "job_id": job.id, "status": job.status,
        "estimated_cost_cents": est,
        "estimated_wait_seconds": 240 if body.model == "sora-2" else 420,
    }


def _job_dict(j: AIJob) -> dict:
    return {
        "id": j.id, "status": j.status, "job_type": j.job_type,
        "input": j.input_json, "output": j.output_json,
        "error_log": j.error_log,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
    }


@router.get("/video/history")
def video_history(
    limit: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    rows = db.query(AIJob).filter(
        AIJob.organization_id == current.organization_id,
        AIJob.job_type == "SORA_VIDEO",
    ).order_by(AIJob.id.desc()).limit(min(limit, 100)).all()
    return {"items": [_job_dict(j) for j in rows]}


@router.get("/video/{job_id}")
def video_status(
    job_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    job = db.query(AIJob).filter(
        AIJob.id == job_id,
        AIJob.organization_id == current.organization_id,
        AIJob.job_type == "SORA_VIDEO",
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return _job_dict(job)


# ─── Nano Banana infographic (sync) ─────────────────────────────────
class VisualIn(BaseModel):
    prompt: str = Field(min_length=8, max_length=2000)
    slide_id: Optional[int] = None
    model: str = "gemini-3.1-flash-image-preview"
    attach_to_slide: bool = True


@router.post("/visuals/generate")
async def generate_visual(
    body: VisualIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Generates a PNG infographic. If `slide_id + attach_to_slide` are set,
    the slide's media_url is updated and slide_type set to IMAGE."""
    est = visuals_service.estimated_cost_cents(body.model)
    ai_budget_service.check_budget(db, current.organization_id,
                                    estimated_cost_cents=est)

    slide = None
    if body.slide_id:
        slide = db.query(CourseSlide).join(Course).filter(
            CourseSlide.id == body.slide_id,
            Course.organization_id == current.organization_id,
        ).first()
        if not slide:
            raise HTTPException(status_code=404, detail="Slide not found")

    result = await visuals_service.generate_infographic(
        prompt=body.prompt, model=body.model, org_id=current.organization_id,
    )
    if slide and body.attach_to_slide:
        slide.media_url = result["url"]
        slide.slide_type = SlideType.IMAGE

    ai_budget_service.record_spend(
        db, organization_id=current.organization_id, user_id=current.id,
        provider="gemini", model=body.model, cost_cents=est,
        input_tokens=len(body.prompt) // 4, output_tokens=0,
    )
    audit_service.record(
        db, current, "AI_VISUAL_GENERATED",
        target_type="slide" if slide else "prompt",
        target_id=str(slide.id) if slide else None,
        metadata={"prompt_len": len(body.prompt), "model": body.model,
                  "size_bytes": result["size_bytes"]},
    )
    db.commit()

    return {
        "url": result["url"], "size_bytes": result["size_bytes"],
        "model": result["model"], "mime_type": result["mime_type"],
        "slide_id": slide.id if slide else None,
        "attached": bool(slide and body.attach_to_slide),
        "cost_cents": est,
    }
