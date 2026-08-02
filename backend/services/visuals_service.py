"""Nano Banana (Gemini) image generation — infographics for slides (Iter 27a).

Sync-ish LLM chat: `LlmChat.send_message_multimodal_response` returns
`(text, images)` where each image is `{mime_type, data}` (base64). We
decode + persist to storage and hand back a URL.

Cost is roughly $0.04 per image on `gemini-3.1-flash-image-preview`.
"""
from __future__ import annotations

import base64
import logging
import uuid
from typing import Optional

from fastapi import HTTPException

from core.config import settings
from services.storage_service import get_storage

logger = logging.getLogger("ifpi.ai.visuals")

_ALLOWED_MODELS = {"gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"}

_SYSTEM_PROMPT = (
    "You are IFPI's visual designer. Produce a clean, on-brand infographic "
    "or diagram that visually communicates the concept described. Prefer "
    "high-contrast, minimal text, education-first composition."
)


def estimated_cost_cents(model: str = "gemini-3.1-flash-image-preview") -> int:
    return 6 if model == "gemini-3-pro-image-preview" else 4


async def generate_infographic(
    prompt: str, *, model: str = "gemini-3.1-flash-image-preview",
    org_id: int,
) -> dict:
    """Generate a single PNG infographic. Returns
    `{url, storage_key, size_bytes, model}` or raises HTTPException.
    """
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="Image generation requires EMERGENT_LLM_KEY")
    if model not in _ALLOWED_MODELS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid model. Use {sorted(_ALLOWED_MODELS)}")
    prompt = (prompt or "").strip()
    if len(prompt) < 8:
        raise HTTPException(status_code=400,
                            detail="Prompt is too short (need at least 8 chars)")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError as e:
        logger.exception("emergentintegrations missing: %s", e)
        raise HTTPException(status_code=503, detail="Image gen unavailable")

    chat = (
        LlmChat(api_key=settings.emergent_llm_key,
                session_id=f"visuals-{uuid.uuid4().hex}",
                system_message=_SYSTEM_PROMPT)
        .with_model("gemini", model)
        .with_params(modalities=["image", "text"])
    )
    try:
        _text, images = await chat.send_message_multimodal_response(
            UserMessage(text=prompt)
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Nano Banana call failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Image generation failed ({type(e).__name__}) — please retry",
        )

    if not images:
        raise HTTPException(status_code=502,
                            detail="AI returned no image — refine your prompt and retry")

    img = images[0]
    b64_data = img.get("data") or ""
    if not b64_data:
        raise HTTPException(status_code=502, detail="AI returned empty image data")
    try:
        img_bytes = base64.b64decode(b64_data)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="AI image data was not valid base64")

    mime = img.get("mime_type") or "image/png"
    ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime else "png")
    key = f"visuals/{org_id}/{uuid.uuid4().hex}.{ext}"
    storage = get_storage()
    url = storage.save(img_bytes, key, content_type=mime)

    return {
        "url": url, "storage_key": key,
        "size_bytes": len(img_bytes),
        "mime_type": mime, "model": model,
    }
