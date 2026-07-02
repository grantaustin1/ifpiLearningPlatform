"""OpenAI TTS narration for slides (Iter 26a).

Wraps `emergentintegrations.llm.openai.OpenAITextToSpeech` with:
- 4096-char guard (OpenAI TTS limit — text is split into up to 6 chunks and
  concatenated, so slide `content` up to ~24000 chars is supported).
- Persistent storage via the pluggable `services.storage_service` backend.
- Cost tracking through `ai_budget_service.record_spend`.

Nothing in this file is Sora- or image-specific — those live in their own
services shipped in a follow-up iteration.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import List, Optional

from fastapi import HTTPException

from core.config import settings
from services.storage_service import get_storage

logger = logging.getLogger("ifpi.ai.tts")

_MAX_TTS_CHARS = 4096
_MAX_CHUNKS = 6           # 6 * 4096 = 24576 chars per slide is plenty
_ALLOWED_MODELS = {"tts-1", "tts-1-hd"}
_ALLOWED_VOICES = {"alloy", "ash", "coral", "echo", "fable",
                   "nova", "onyx", "sage", "shimmer"}


def _chunk_text(text: str, chunk_size: int = _MAX_TTS_CHARS) -> List[str]:
    """Split on sentence boundaries when possible, hard-cut at chunk_size."""
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks: List[str] = []
    while text and len(chunks) < _MAX_CHUNKS:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        # Prefer a sentence-ending punctuation in the last quarter of the slice
        window_start = max(0, chunk_size - chunk_size // 4)
        window = text[window_start:chunk_size]
        m = re.search(r"[.!?]\s", window[::-1])
        if m:
            cut = chunk_size - m.start()
        else:
            # No sentence break — try a space
            sp = text.rfind(" ", window_start, chunk_size)
            cut = sp if sp > 0 else chunk_size
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return [c for c in chunks if c]


async def generate_narration(
    text: str, *, model: str = "tts-1", voice: str = "nova",
    org_id: int, slide_id: Optional[int] = None,
) -> dict:
    """Generate a single MP3 narration for `text`. Returns
    `{url, size_bytes, chunk_count, model, voice}`. Raises HTTPException on
    misconfig or provider failure.
    """
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="Narration requires EMERGENT_LLM_KEY")
    if model not in _ALLOWED_MODELS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid model. Choose from {sorted(_ALLOWED_MODELS)}")
    if voice not in _ALLOWED_VOICES:
        raise HTTPException(status_code=400,
                            detail=f"Invalid voice. Choose from {sorted(_ALLOWED_VOICES)}")

    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")
    chunks = _chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Text is too short after cleanup")

    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
    except ImportError as e:
        logger.exception("emergentintegrations missing: %s", e)
        raise HTTPException(status_code=503, detail="TTS integration not available")

    tts = OpenAITextToSpeech(api_key=settings.emergent_llm_key)

    audio_parts: List[bytes] = []
    for i, chunk in enumerate(chunks):
        try:
            audio = await tts.generate_speech(
                text=chunk, model=model, voice=voice,
            )
        except Exception as e:   # noqa: BLE001
            logger.exception("TTS chunk %s failed: %s", i, e)
            raise HTTPException(
                status_code=502,
                detail=f"TTS generation failed at chunk {i + 1}: {type(e).__name__}",
            )
        if not audio:
            raise HTTPException(status_code=502, detail="TTS returned empty audio")
        audio_parts.append(audio)

    # MP3 frames are self-synchronising — concatenation works cleanly for
    # short back-to-back narration files. If you switch to WAV you'll want
    # a proper joiner (each WAV has its own RIFF header).
    combined = b"".join(audio_parts)

    key = f"narration/{org_id}/{uuid.uuid4().hex}.mp3"
    storage = get_storage()
    url = storage.save(combined, key, content_type="audio/mpeg")

    return {
        "url": url,
        "storage_key": key,
        "size_bytes": len(combined),
        "chunk_count": len(chunks),
        "model": model,
        "voice": voice,
        "slide_id": slide_id,
    }


def estimated_cost_cents(text: str, model: str = "tts-1") -> int:
    """OpenAI TTS pricing (Feb 2026):
        tts-1     $0.015 / 1K chars → 1.5c per 1K chars
        tts-1-hd  $0.030 / 1K chars → 3.0c per 1K chars
    """
    chars = len((text or "").strip())
    rate = 3 if model == "tts-1-hd" else 1.5
    return max(1, int((chars / 1000) * rate))
