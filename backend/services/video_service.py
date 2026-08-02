"""Sora 2 video overview generation (Iter 26b).

`emergentintegrations.llm.openai.video_generation.OpenAIVideoGeneration.text_to_video`
is synchronous and blocks 2-5 minutes per call. We wrap it in a background
worker so API requests return immediately with an `AIJob` id. The frontend
polls the job endpoint until COMPLETED or FAILED.

Cost model (approximate USD per generation — used for budget preflight):
  sora-2, 4s     → 40¢
  sora-2, 8s     → 80¢
  sora-2, 12s    → $1.20
  sora-2-pro, 4s → $1.20
  sora-2-pro, 8s → $2.40
  sora-2-pro, 12s→ $3.60
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import HTTPException

from core.config import settings
from services.storage_service import get_storage

logger = logging.getLogger("ifpi.ai.sora")

_ALLOWED_MODELS = {"sora-2", "sora-2-pro"}
_ALLOWED_SIZES = {"1280x720", "1792x1024", "1024x1792", "1024x1024"}
_ALLOWED_DURATIONS = {4, 8, 12}


def estimated_cost_cents(model: str, duration: int) -> int:
    """Approximate per-video cost in cents. Numbers are aligned with the
    typical Sora 2 pricing so the org budget check gates absurd requests
    early."""
    per_sec_cents = 30 if model == "sora-2-pro" else 10
    return max(1, per_sec_cents * duration)


def validate_params(model: str, size: str, duration: int) -> None:
    if model not in _ALLOWED_MODELS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid model. Use {sorted(_ALLOWED_MODELS)}")
    if size not in _ALLOWED_SIZES:
        raise HTTPException(status_code=400,
                            detail=f"Invalid size. Use {sorted(_ALLOWED_SIZES)}")
    if duration not in _ALLOWED_DURATIONS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid duration. Use {sorted(_ALLOWED_DURATIONS)}")


def generate_video_sync(prompt: str, *, model: str, size: str, duration: int,
                         org_id: int, max_wait_seconds: int = 600) -> dict:
    """Blocking Sora 2 call — spawn from a background worker only. Returns
    `{url, storage_key, size_bytes, model, size, duration}` or raises.
    """
    if not settings.emergent_llm_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    try:
        from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration
    except ImportError as e:
        raise RuntimeError(f"emergentintegrations missing: {e}")

    video_gen = OpenAIVideoGeneration(api_key=settings.emergent_llm_key)
    video_bytes = video_gen.text_to_video(
        prompt=prompt, model=model, size=size, duration=duration,
        max_wait_time=max_wait_seconds,
    )
    if not video_bytes:
        raise RuntimeError("Sora returned empty video bytes")

    key = f"video/{org_id}/{uuid.uuid4().hex}.mp4"
    storage = get_storage()
    url = storage.save(video_bytes, key, content_type="video/mp4")
    return {
        "url": url, "storage_key": key,
        "size_bytes": len(video_bytes),
        "model": model, "size": size, "duration": duration,
    }
