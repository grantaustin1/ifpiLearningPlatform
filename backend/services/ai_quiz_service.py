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
from typing import List, Optional

from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger("ifpi.ai_quiz")


_SYSTEM_PROMPT = (
<<<<<<< HEAD
    "You are a fitness-industry education expert who writes high-quality exam "
=======
    "You are a music-industry education expert who writes high-quality exam "
>>>>>>> origin/main
    "questions. Output STRICT JSON only — no commentary, no markdown fences."
)

_TYPE_RULES = {
    "MULTIPLE_CHOICE": (
        "EXACTLY 4 plausible options per question; correct_answer must be the "
        "EXACT text of one option (not 'A'/'B')."
    ),
    "TRUE_FALSE": (
        "Each question must be a single factual statement. Set options to "
        "[\"True\", \"False\"] and correct_answer to the right value."
    ),
    "SHORT_ANSWER": (
        "Open-ended. options must be an empty list []. correct_answer is the "
        "expected answer (a short phrase). Include an explanation."
    ),
    "MIXED": (
        "Use a mix of MULTIPLE_CHOICE, TRUE_FALSE, and SHORT_ANSWER. Add a "
        "`question_type` field per question with one of those three values."
    ),
}


def _build_prompt(course_title: str, slide_excerpts: List[dict], num_questions: int,
                  question_type: str = "MULTIPLE_CHOICE",
                  avoid_topics: Optional[List[str]] = None) -> str:
    excerpt_block = "\n\n".join(
        f"Slide {i+1}: {s.get('title','')}\n{(s.get('content_text') or '')[:600]}"
        for i, s in enumerate(slide_excerpts)
    )
    type_rule = _TYPE_RULES.get(question_type, _TYPE_RULES["MULTIPLE_CHOICE"])
    avoid = ""
    if avoid_topics:
        avoid = ("\n\nAVOID rephrasing any of these existing questions; pick a "
                 "different concept from the material:\n- " +
                 "\n- ".join(avoid_topics[:20]))
    structure = """{
  "questions": [
    {
      "question_text": "string",
      "question_type": "MULTIPLE_CHOICE | TRUE_FALSE | SHORT_ANSWER",
      "options": ["..."],
      "correct_answer": "string",
      "explanation": "1-2 sentences"
    }
  ]
}"""
    return (
        f'Generate EXACTLY {num_questions} {question_type} exam question(s) for '
        f'the course "{course_title}". {type_rule}\n'
        f"Every question must test understanding, not rote recall.{avoid}\n\n"
        f"Course material:\n\n{excerpt_block}\n\n"
        f"Output ONLY this JSON shape:\n{structure}"
    )


async def generate_questions(
    course_title: str, slides: List[dict], num_questions: int = 5,
    question_type: str = "MULTIPLE_CHOICE",
    avoid_topics: Optional[List[str]] = None,
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

    prompt = _build_prompt(course_title, slides, num_questions,
                           question_type=question_type, avoid_topics=avoid_topics)
    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception("AI quiz LLM call failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"AI generation failed ({type(e).__name__}) — please retry",
        )

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
        qtype = str(q.get("question_type") or question_type).upper()
        if qtype not in ("MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER"):
            qtype = "MULTIPLE_CHOICE"
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        correct = str(q.get("correct_answer") or "").strip()
        if not (question_text and correct):
            continue
        if qtype == "MULTIPLE_CHOICE":
            if len(options) < 2:
                continue
            # If the model put correct_answer as "A"/"B" — coerce
            if len(correct) == 1 and correct.upper() in "ABCD":
                idx = "ABCD".index(correct.upper())
                if idx < len(options):
                    correct = options[idx]
            if correct not in options:
                match = next((o for o in options if correct.lower() in o.lower()), None)
                if match is None:
                    continue
                correct = match
            options = options[:4]
        elif qtype == "TRUE_FALSE":
            options = ["True", "False"]
            # Normalise correct to True/False label
            c = correct.strip().lower()
            if c in ("true", "t", "yes"):
                correct = "True"
            elif c in ("false", "f", "no"):
                correct = "False"
            else:
                continue
        else:  # SHORT_ANSWER
            options = []
        out.append({
            "question_text": question_text,
            "question_type": qtype,
            "options": options,
            "correct_answer": correct,
            "explanation": str(q.get("explanation") or "").strip()[:500],
        })
    if not out:
        raise HTTPException(status_code=502,
                            detail="AI returned no valid questions — please retry")
    return out
