"""AI quiz generator — turn course slide content into multiple-choice questions.

Uses the Emergent LLM key (same provider/model the AI course builder uses).
Output schema is enforced via a strict JSON prompt so the calling endpoint
can rely on `questions[].question_text / options / correct_answer / explanation`.

This service does NOT write to the DB — it returns a JSON payload the admin
can review on the frontend before bulk-inserting into the course's exam.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import List

from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger("ifpi.ai_quiz")


_SYSTEM_PROMPT = (
    "You are a music-industry education expert who writes high-quality "
    "multiple-choice exam questions. Every option must be plausible — no "
    "throwaway distractors. Output STRICT JSON only — no commentary, no "
    "markdown fences, no explanations outside the JSON."
)


def _build_prompt(course_title: str, slide_excerpts: List[dict], num_questions: int) -> str:
    excerpt_block = "\n\n".join(
        f"Slide {i+1}: {s.get('title','')}\n{(s.get('content_text') or '')[:600]}"
        for i, s in enumerate(slide_excerpts)
    )
    structure = """{
  "questions": [
    {
      "question_text": "string",
      "options": ["option A", "option B", "option C", "option D"],
      "correct_answer": "option A",
      "explanation": "1-2 sentences explaining why the correct answer is correct"
    }
  ]
}"""
    return (
        f'Generate EXACTLY {num_questions} multiple-choice questions for the course '
        f'"{course_title}". Each question must:\n'
        f"- Test understanding, not rote recall.\n"
        f"- Have EXACTLY 4 options.\n"
        f"- Include the EXACT correct option text in `correct_answer` (not just A/B/C/D).\n"
        f"- Cover different slides where possible.\n\n"
        f"Course material:\n\n{excerpt_block}\n\n"
        f"Output ONLY this JSON shape:\n{structure}"
    )


async def generate_questions(
    course_title: str, slides: List[dict], num_questions: int = 5,
) -> List[dict]:
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="AI quiz requires EMERGENT_LLM_KEY")
    if not slides:
        raise HTTPException(status_code=400,
                            detail="Course has no slides — add some lessons first")
    if not (1 <= num_questions <= 20):
        raise HTTPException(status_code=400, detail="num_questions must be 1-20")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError as e:
        logger.exception("emergentintegrations not installed: %s", e)
        raise HTTPException(status_code=503, detail="AI integration not available")

    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"ai-quiz-{uuid.uuid4().hex}",
        system_message=_SYSTEM_PROMPT,
    ).with_model(settings.ai_builder_provider, settings.ai_builder_model)

    prompt = _build_prompt(course_title, slides, num_questions)
    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception("AI quiz LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail="AI generation failed — please retry")

    text = (raw if isinstance(raw, str) else getattr(raw, "content", str(raw))).strip()
    # Strip code fences the model may have added despite the prompt
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.error("AI quiz returned non-JSON: %s", text[:500])
        raise HTTPException(status_code=502, detail="AI returned invalid JSON — please retry")

    raw_qs = parsed.get("questions") or []
    out: List[dict] = []
    for q in raw_qs:
        question_text = str(q.get("question_text") or "").strip()
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        correct = str(q.get("correct_answer") or "").strip()
        if not (question_text and len(options) >= 2 and correct):
            continue
        # If the model put correct_answer as "A"/"B" — coerce
        if len(correct) == 1 and correct.upper() in "ABCD":
            idx = "ABCD".index(correct.upper())
            if idx < len(options):
                correct = options[idx]
        # Ensure the correct answer actually appears in the options list
        if correct not in options:
            # Best-effort substring match — otherwise drop the question
            match = next((o for o in options if correct.lower() in o.lower()), None)
            if match is None:
                continue
            correct = match
        out.append({
            "question_text": question_text,
            "options": options[:4],
            "correct_answer": correct,
            "explanation": str(q.get("explanation") or "").strip()[:500],
        })
    if not out:
        raise HTTPException(status_code=502,
                            detail="AI returned no valid questions — please retry")
    return out
