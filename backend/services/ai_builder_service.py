"""AI course-builder service.

Uses `emergentintegrations` with EMERGENT_LLM_KEY. JSON-mode prompt; one-shot
generate (non-streaming) — the caller commits the result atomically into the
DB after the user clicks "Apply".
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List

from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "You are an expert instructional designer. Generate clear, educational content "
    "in JSON format. Output ONLY valid JSON — no markdown, no prose, no code fences."
)


def _build_user_prompt(topic: str, description: str, num_slides: int,
                       include_quiz: bool, num_questions: int) -> str:
    quiz_block = (
        f"\n\nAlso generate {num_questions} multiple-choice quiz questions to assess "
        f"understanding. Each question must have exactly 4 options (A, B, C, D), one "
        f"correct answer, and a brief explanation."
        if include_quiz else ""
    )
    structure = '''{
  "slides": [
    {
      "title": "slide title",
      "content": "HTML for this slide (use <h2>, <p>, <ul>/<li>, <strong> — 150-300 words)",
      "slide_type": "TEXT",
      "order_index": 1
    }
  ]'''
    if include_quiz:
        structure += ''',
  "questions": [
    {
      "question_text": "question text",
      "question_type": "MULTIPLE_CHOICE",
      "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
      "correct_answer": "0",
      "explanation": "why this answer is correct",
      "points": 1,
      "order_index": 1
    }
  ]'''
    structure += "\n}"

    extra = f"\n\nAdditional context: {description.strip()}" if description else ""
    return (
        f'Create a course about: "{topic.strip()}"{extra}\n\n'
        f"Generate exactly {num_slides} course slides. Each slide is a self-contained lesson "
        f"section.{quiz_block}\n\nOutput EXACTLY this JSON structure (nothing else):\n{structure}"
    )


async def generate_course(topic: str, description: str, num_slides: int,
                          include_quiz: bool, num_questions: int) -> Dict:
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="AI builder requires EMERGENT_LLM_KEY")
    try:
        # Import here so a missing optional dep doesn't crash the whole app
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError as e:
        logger.exception("emergentintegrations not installed: %s", e)
        raise HTTPException(status_code=503, detail="AI integration not available")

    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"ai-builder-{uuid.uuid4().hex}",
        system_message=_SYSTEM_PROMPT,
    ).with_model(settings.ai_builder_provider, settings.ai_builder_model)

    prompt = _build_user_prompt(topic, description, num_slides, include_quiz, num_questions)
    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception("AI builder LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail="AI generation failed — please retry")

    text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))

    # Strip code fences if the model added them despite the prompt
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.error("AI builder returned non-JSON: %s", text[:500])
        raise HTTPException(status_code=502, detail="AI returned invalid JSON — please retry")

    slides: List[Dict] = []
    for i, s in enumerate(parsed.get("slides", [])):
        slides.append({
            "title": str(s.get("title") or f"Slide {i + 1}").strip(),
            "content": str(s.get("content") or "").strip(),
            "slide_type": "TEXT",
            "order_index": i + 1,
        })

    questions: List[Dict] = []
    if include_quiz:
        for i, q in enumerate(parsed.get("questions", [])):
            opts = q.get("options") or []
            if not isinstance(opts, list):
                opts = []
            ca = q.get("correct_answer")
            # Coerce to index-as-string for our grader
            if isinstance(ca, int):
                ca = str(ca)
            elif isinstance(ca, str) and not ca.isdigit():
                # Try to find the matching option
                try:
                    ca = str(opts.index(ca))
                except ValueError:
                    # Fall back to first option to avoid grading errors
                    ca = "0"
            questions.append({
                "question_text": str(q.get("question_text") or "").strip(),
                "question_type": "MULTIPLE_CHOICE",
                "options": [str(o) for o in opts],
                "correct_answer": str(ca or "0"),
                "explanation": str(q.get("explanation") or "").strip(),
                "points": int(q.get("points") or 1),
                "order_index": i + 1,
            })

    return {"slides": slides, "questions": questions}
