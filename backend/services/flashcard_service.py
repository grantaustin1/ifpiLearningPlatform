"""Flashcard AI generation + SM-2 spaced-repetition scheduler (Iter 25).

Two responsibilities in one module:

1. `generate_flashcards(...)`
   Uses the Emergent LLM key (same provider as ai_quiz_service) to turn
   course-slide content (optionally augmented by SourceChunks from the
   AI tutor's RAG store) into a batch of grounded flashcards. Returns a
   preview payload — no DB writes.

2. `apply_sm2(quality, ease, interval, reps)`
   Pure SM-2 algorithm — takes a 0-5 quality rating + current state,
   returns `(new_ease, new_interval_days, new_repetitions, next_review_at)`.
   No IO, easy to unit-test.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger("ifpi.ai.flashcards")

_SYSTEM_PROMPT = (
    "You are IFPI's course-authoring assistant. Turn the provided course "
    "material into concise flashcards. Output STRICT JSON only — no "
    "commentary, no markdown fences."
)


def _build_prompt(course_title: str, slides: List[dict], count: int,
                  extra_context: Optional[str] = None) -> str:
    excerpt_block = "\n\n".join(
        f"Slide {i + 1}: {s.get('title', '')}\n{(s.get('content') or '')[:800]}"
        for i, s in enumerate(slides)
    )
    ctx = f"\n\nAdditional grounded context:\n{extra_context[:4000]}" if extra_context else ""
    structure = """{
  "cards": [
    {
      "front": "short question or prompt (max ~15 words)",
      "back": "concise answer (1-3 sentences)",
      "hint": "optional short hint (< 12 words)",
      "difficulty": 1,
      "tags": ["topic-1", "topic-2"]
    }
  ]
}"""
    return (
        f'Generate EXACTLY {count} flashcards for the course "{course_title}". '
        f"Each card MUST be answerable from the material below alone. Do NOT "
        f"invent people, dates, or numbers. Prefer conceptual understanding "
        f"over rote recall. Set difficulty 1 (easy) — 5 (hard).\n\n"
        f"Course material:\n\n{excerpt_block}{ctx}\n\n"
        f"Output ONLY this JSON shape:\n{structure}"
    )


async def generate_flashcards(
    course_title: str, slides: List[dict], count: int = 8,
    extra_context: Optional[str] = None,
) -> List[dict]:
    """Return a list of `{front, back, hint, difficulty, tags}` dicts. Caller
    is responsible for reviewing and persisting them via the bulk-save endpoint.
    """
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="Flashcards require EMERGENT_LLM_KEY")
    if not slides:
        raise HTTPException(status_code=400,
                            detail="No slides provided — pick at least one")
    if not (1 <= count <= 40):
        raise HTTPException(status_code=400, detail="count must be 1-40")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError as e:
        logger.exception("emergentintegrations not installed: %s", e)
        raise HTTPException(status_code=503, detail="AI integration not available")

    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"flashcards-{uuid.uuid4().hex}",
        system_message=_SYSTEM_PROMPT,
    ).with_model(settings.ai_builder_provider, settings.ai_builder_model)

    prompt = _build_prompt(course_title, slides, count, extra_context)
    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:  # noqa: BLE001
        logger.exception("Flashcard LLM call failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Flashcard generation failed ({type(e).__name__}) — please retry",
        )

    text = (raw if isinstance(raw, str) else getattr(raw, "content", str(raw))).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Flashcards returned non-JSON: %s", text[:500])
        raise HTTPException(status_code=502,
                            detail="AI returned invalid JSON — please retry")

    raw_cards = parsed.get("cards") or []
    out: List[dict] = []
    for c in raw_cards:
        front = str(c.get("front") or "").strip()[:500]
        back = str(c.get("back") or "").strip()
        if not (front and back):
            continue
        difficulty_raw = c.get("difficulty", 2)
        try:
            difficulty = max(1, min(5, int(difficulty_raw)))
        except (TypeError, ValueError):
            difficulty = 2
        tags = c.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).strip()[:40] for t in tags if str(t).strip()][:6]
        out.append({
            "front": front,
            "back": back[:2000],
            "hint": (str(c.get("hint") or "").strip()[:300] or None),
            "difficulty": difficulty,
            "tags": tags,
        })
    if not out:
        raise HTTPException(status_code=502,
                            detail="AI returned no valid cards — please retry")
    return out


# ── SM-2 algorithm ──────────────────────────────────────────────────
# Reference: Piotr Wozniak, SuperMemo-2 (1987).
# quality: 0-5 (0=complete blackout, 5=perfect recall).
# Returns: (new_ease_factor, new_interval_days, new_repetitions).
_MIN_EASE = 1.3


def apply_sm2(
    quality: int, ease: float, interval_days: int, repetitions: int,
) -> Tuple[float, int, int, datetime]:
    """Pure function — no IO. Given quality (0-5) and current SM-2 state,
    returns `(new_ease, new_interval, new_reps, next_review_at_utc)`.
    """
    if quality < 0 or quality > 5:
        raise ValueError("quality must be 0-5")

    q = int(quality)
    # Wrong answer (< 3) resets the interval schedule per SM-2
    if q < 3:
        new_reps = 0
        new_interval = 1
    else:
        new_reps = repetitions + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            new_interval = max(1, round(interval_days * ease))

    # Ease factor update (SM-2 formula)
    new_ease = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if new_ease < _MIN_EASE:
        new_ease = _MIN_EASE

    next_review = datetime.now(timezone.utc) + timedelta(days=new_interval)
    return round(new_ease, 4), new_interval, new_reps, next_review
