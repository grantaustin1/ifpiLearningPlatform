"""Source-grounded AI tutor service (Iter 23).

Given a staff question + top-k retrieved chunks, ask Claude Sonnet (via
Emergent LLM Key) to answer using ONLY the sources. Every answer is
required to cite chunks by their token like `[S1]`, `[S2]`. If no source
supports the question, the assistant must refuse rather than hallucinate.

PII redaction is applied to the user's question AND every retrieved chunk
before the prompt goes out — locked policy (b) from the roadmap. Staff
with ADMIN/SUPER_ADMIN can disable via `pii_redact=false` on the request.
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from services import embedding_service
from services.pii_redactor import redact_many, unredact

logger = logging.getLogger("ifpi.tutor")


_TUTOR_SYSTEM = """\
You are IFPI's course-authoring assistant. You help course designers write \
accurate, well-sourced training content.

RULES you MUST follow:
1. Answer using ONLY the sources provided below. Do NOT use outside knowledge.
2. Cite every claim inline with the source token, e.g. [S1] or [S2, S3].
3. If the sources do NOT contain enough information to answer, say so \
explicitly ("The provided sources don't cover this") — do NOT guess.
4. Be concise. Prefer bullet points for lists. Use short paragraphs.
5. Never invent people, dates, numbers, or citations.
"""


async def tutor_answer(
    db: Session, *,
    organization_id: int,
    user_id: int,
    question: str,
    course_id: Optional[int] = None,
    top_k: int = 5,
    pii_redact: bool = True,
) -> dict:
    """Return `{answer, citations, redaction_applied, sources_used: int}`.
    Raises HTTPException 503 if EMERGENT_LLM_KEY is unset."""
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
            detail="Tutor requires EMERGENT_LLM_KEY — set it in backend/.env")

    # 1. Retrieve top-k chunks from the org's source library
    hits = await embedding_service.semantic_search(
        db, organization_id=organization_id, query=question,
        top_k=top_k, course_id=course_id,
    )
    if not hits:
        return {
            "answer": ("I couldn't find any relevant sources in your library. "
                       "Upload a PDF/DOCX (Sources tab) or run a Deep Research, "
                       "then ask again."),
            "citations": [], "sources_used": 0,
            "redaction_applied": False, "no_sources": True,
        }

    # 2. Optional PII redaction of question + chunks (default ON per policy b)
    mapping: dict = {}
    if pii_redact:
        pieces = [question] + [h["text"] for h in hits]
        redacted, mapping, _counts = redact_many(*pieces)
        redacted_question = redacted[0]
        redacted_chunk_texts = redacted[1:]
    else:
        redacted_question = question
        redacted_chunk_texts = [h["text"] for h in hits]

    # 3. Build the prompt
    sources_block = "\n\n".join(
        f"[S{i + 1}] (doc: {h['document_title']!r}, chunk {h['chunk_index']})\n{ct}"
        for i, (h, ct) in enumerate(zip(hits, redacted_chunk_texts))
    )
    user_prompt = (
        f"QUESTION:\n{redacted_question}\n\n"
        f"SOURCES:\n{sources_block}\n\n"
        f"Answer the question using only the sources above. "
        f"Cite claims like [S1]. If sources don't cover it, say so."
    )

    # 4. Dispatch to Claude Sonnet via emergentintegrations
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(status_code=503, detail="AI integration not available")

    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"tutor-{uuid.uuid4().hex}",
        system_message=_TUTOR_SYSTEM,
    ).with_model(settings.tutor_llm_provider, settings.tutor_llm_model)

    try:
        import asyncio
        raw = await asyncio.wait_for(
            chat.send_message(UserMessage(text=user_prompt)), timeout=60)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504,
                            detail="Tutor took too long to answer — please retry")
    except Exception as e:   # noqa: BLE001
        logger.exception("Tutor LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail="Tutor generation failed — please retry")

    answer_redacted = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
    answer_final = unredact(answer_redacted.strip(), mapping) if pii_redact else answer_redacted.strip()

    # 5. Record cost (rough estimate — Emergent proxy doesn't return usage
    # tokens on every call, so we approximate)
    try:
        from services import ai_budget_service
        approx_tokens_in = sum(max(1, len(t) // 4) for t in [user_prompt])
        approx_tokens_out = max(1, len(answer_final) // 4)
        # $0.15 / 1M input tokens + $0.60 / 1M output tokens for gpt-4o-mini
        cost_cents = int(
            approx_tokens_in * 0.00015 / 10 + approx_tokens_out * 0.0006 / 10,
        )
        ai_budget_service.record_spend(
            db, organization_id=organization_id, user_id=user_id,
            provider=settings.tutor_llm_provider, model=settings.tutor_llm_model,
            cost_cents=cost_cents, input_tokens=approx_tokens_in,
            output_tokens=approx_tokens_out,
        )
        db.commit()
    except Exception:   # noqa: BLE001
        logger.exception("Failed to record tutor spend — continuing")
        db.rollback()

    citations = [
        {"token": f"S{i + 1}", "chunk_id": h["chunk_id"],
         "document_id": h["document_id"], "document_title": h["document_title"],
         "chunk_index": h["chunk_index"], "score": h["score"]}
        for i, h in enumerate(hits)
    ]
    return {
        "answer": answer_final,
        "citations": citations,
        "sources_used": len(hits),
        "redaction_applied": bool(mapping) if pii_redact else False,
        "no_sources": False,
    }
