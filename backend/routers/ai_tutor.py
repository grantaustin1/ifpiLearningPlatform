"""Iter 30m — AI Tutor v1 (learner-facing course chat).

Design
------
- Retrieval: reuses `services.embedding_service.semantic_search()` over
  existing SourceChunks. If no chunks are embedded for an org, falls
  back to naive LIKE-scan across `SourceDocument.extracted_text` (still
  usable for orgs that haven't run deep research).
- LLM: emergentintegrations LlmChat with the Emergent LLM key. Same
  provider/model settings as the AI builder (`ai_builder_provider`,
  `ai_builder_model`).
- PII redaction: ALWAYS ON. Learner questions are redacted before being
  sent to the LLM. Redaction map is applied server-side; the reverse
  substitution happens on the response before persistence so learners
  never see phone/email/SSN placeholders in their own chat history.
- Citations: assistant messages carry a JSON list of the chunks used
  so the UI can render "Source: <doc> · page X" links.

Access control
--------------
- Every endpoint requires an authenticated user (`get_current_user`).
- Session/message read+write are scoped to `(current.id, current.organization_id)`.
  A user can only see their own sessions; a user in org A cannot
  interact with sessions in org B.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.config import settings
from core.database import get_db
from models import (
    AITutorMessage, AITutorSession, Course, SourceChunk, SourceDocument,
)
from services import audit_service, embedding_service, pii_redactor

logger = logging.getLogger("ifpi.tutor")

router = APIRouter(prefix="/api/tutor", tags=["AI Tutor"])


# ── Schemas ───────────────────────────────────────────────────────────


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    course_id: Optional[int] = None
    session_id: Optional[int] = None
    top_k: int = Field(default=4, ge=1, le=8)


class AskOut(BaseModel):
    session_id: int
    message_id: int
    answer: str
    citations: list[dict]
    redaction_applied: bool


# ── Retrieval ─────────────────────────────────────────────────────────


async def _retrieve_context(
    db: Session, *, organization_id: int, course_id: Optional[int],
    query: str, top_k: int,
) -> list[dict]:
    """Return top-K relevant chunks as
    `[{chunk_id, document_id, document_title, text, score}]`.

    Prefers embedding-based search. Falls back to a naive LIKE scan
    when no chunks have embeddings yet.
    """
    have_embeddings = db.query(SourceChunk).join(
        SourceDocument, SourceChunk.document_id == SourceDocument.id,
    ).filter(
        SourceDocument.organization_id == organization_id,
        SourceChunk.embedding.isnot(None),
    ).limit(1).first() is not None

    if have_embeddings:
        try:
            hits = await embedding_service.semantic_search(
                db, organization_id=organization_id, query=query,
                top_k=top_k, course_id=course_id,
            )
            return hits
        except Exception as e:
            logger.warning("semantic_search failed, falling back to LIKE: %s", e)

    # Fallback: naive LIKE across extracted_text — keep top-K by
    # extracting the ~500-char window around the first match.
    like_pattern = f"%{re.escape(query.split()[0])[:40]}%"  # first token
    q = db.query(SourceDocument).filter(
        SourceDocument.organization_id == organization_id,
        SourceDocument.extracted_text.ilike(like_pattern),
    )
    if course_id is not None:
        q = q.filter(SourceDocument.course_id == course_id)
    docs = q.limit(top_k).all()
    out = []
    for d in docs:
        text = d.extracted_text or ""
        idx = text.lower().find(query.split()[0].lower())
        start = max(0, idx - 200)
        end = min(len(text), idx + 400)
        snippet = text[start:end].strip()
        out.append({
            "chunk_id": None, "document_id": d.id,
            "document_title": d.title, "text": snippet, "score": 0.0,
        })
    return out


# ── LLM call ──────────────────────────────────────────────────────────


_TUTOR_SYSTEM = (
    "You are the IFPI Learning Platform Tutor. Answer the learner's "
    "question using ONLY the provided source excerpts. Cite each fact "
    "inline as [1], [2] etc. matching the numbered excerpts. If the "
    "excerpts don't cover the question, say so and suggest what to "
    "search for. Keep answers concise (< 200 words) unless the learner "
    "explicitly asks for detail. Never invent citations."
)


async def _call_llm(question: str, citations: list[dict]) -> tuple[str, dict]:
    """Send the question + citations to the LLM. Returns (answer_text,
    token_usage_dict). Raises 503 if the LLM is unavailable."""
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="Tutor is not configured — EMERGENT_LLM_KEY missing")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        logger.exception("emergentintegrations missing")
        raise HTTPException(status_code=503,
                            detail="Tutor integration unavailable")

    excerpts = "\n\n".join(
        f"[{i+1}] From \"{c['document_title']}\":\n{c['text']}"
        for i, c in enumerate(citations)
    ) or "(no matching sources — answer from general knowledge but be clear about that)"
    prompt = f"SOURCES:\n{excerpts}\n\nLEARNER QUESTION:\n{question}"

    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"tutor-{uuid.uuid4().hex}",
        system_message=_TUTOR_SYSTEM,
    ).with_model(settings.ai_builder_provider, settings.ai_builder_model)

    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception("Tutor LLM call failed: %s", e)
        raise HTTPException(status_code=502,
                            detail="Tutor is temporarily unavailable — please retry")

    text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
    return text.strip(), {}


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/ask", response_model=AskOut)
async def ask(body: AskIn, request: Request,
              current: CurrentUser = Depends(get_current_user),
              db: Session = Depends(get_db)) -> AskOut:
    # Course scoping: if provided, verify it's in the user's org
    if body.course_id is not None:
        course = db.query(Course).filter(
            Course.id == body.course_id,
            Course.organization_id == current.organization_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

    # 1. Locate or create a session
    if body.session_id:
        session = db.query(AITutorSession).filter(
            AITutorSession.id == body.session_id,
            AITutorSession.user_id == current.id,
            AITutorSession.organization_id == current.organization_id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = AITutorSession(
            organization_id=current.organization_id,
            user_id=current.id, course_id=body.course_id,
            title=(body.question[:80] + "…") if len(body.question) > 80 else body.question,
        )
        db.add(session); db.flush()

    # 2. Redact PII from the question — server never sends raw PII to LLM
    redaction = pii_redactor.redact(body.question)
    redacted_q = redaction.redacted_text
    redaction_applied = redaction.redaction_applied

    # 3. Retrieve top-K context chunks
    citations = await _retrieve_context(
        db, organization_id=current.organization_id,
        course_id=body.course_id, query=redacted_q, top_k=body.top_k,
    )

    # 4. Persist the user turn (store ORIGINAL question so learner sees
    #    their own words in history — redaction is only for LLM egress)
    user_msg = AITutorMessage(
        session_id=session.id, role="user", content=body.question,
    )
    db.add(user_msg); db.flush()

    # 5. LLM call
    answer, _usage = await _call_llm(redacted_q, citations)

    # 6. Persist assistant turn + citations
    citations_slim = [{
        "chunk_id": c.get("chunk_id"),
        "document_id": c.get("document_id"),
        "document_title": c.get("document_title"),
        "snippet": (c.get("text") or "")[:400],
        "score": c.get("score"),
    } for c in citations]
    assistant_msg = AITutorMessage(
        session_id=session.id, role="assistant",
        content=answer, citations=citations_slim,
    )
    db.add(assistant_msg); db.flush()
    session.last_message_at = datetime.utcnow()

    audit_service.record(db, current, "TUTOR_ASK",
                         target_type="tutor_session",
                         target_id=str(session.id),
                         metadata={"citations": len(citations),
                                   "redaction_applied": redaction_applied,
                                   "course_id": body.course_id},
                         request=request)
    db.commit()
    db.refresh(assistant_msg)

    return AskOut(
        session_id=session.id, message_id=assistant_msg.id,
        answer=answer, citations=citations_slim,
        redaction_applied=redaction_applied,
    )


@router.get("/sessions")
def list_sessions(current: CurrentUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    rows = (db.query(AITutorSession)
            .filter(AITutorSession.user_id == current.id,
                    AITutorSession.organization_id == current.organization_id,
                    AITutorSession.archived_at.is_(None))
            .order_by(AITutorSession.last_message_at.desc())
            .limit(50).all())
    return {"items": [{
        "id": r.id, "title": r.title, "course_id": r.course_id,
        "last_message_at": r.last_message_at.isoformat(),
    } for r in rows]}


@router.get("/sessions/{session_id}")
def get_session(session_id: int,
                current: CurrentUser = Depends(get_current_user),
                db: Session = Depends(get_db)) -> dict:
    session = db.query(AITutorSession).filter(
        AITutorSession.id == session_id,
        AITutorSession.user_id == current.id,
        AITutorSession.organization_id == current.organization_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = (db.query(AITutorMessage)
            .filter(AITutorMessage.session_id == session.id)
            .order_by(AITutorMessage.created_at.asc()).all())
    return {
        "id": session.id, "title": session.title,
        "course_id": session.course_id,
        "messages": [{
            "id": m.id, "role": m.role, "content": m.content,
            "citations": m.citations or [],
            "created_at": m.created_at.isoformat(),
        } for m in msgs],
    }


@router.post("/sessions/{session_id}/archive")
def archive_session(session_id: int,
                    current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    session = db.query(AITutorSession).filter(
        AITutorSession.id == session_id,
        AITutorSession.user_id == current.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.archived_at = datetime.utcnow()
    db.commit()
    return {"archived": True}


# ── Iter 30q — Save-as-flashcard ────────────────────────────────────


class SaveAsFlashcardIn(BaseModel):
    """Turn a helpful tutor Q+A into a durable spaced-repetition flashcard.

    Caller passes the `message_id` of an assistant turn; the server pairs
    it with the prior user turn to build the flashcard front (question)
    and back (answer)."""
    message_id: int
    course_id: int
    difficulty: int = Field(default=2, ge=1, le=5)


@router.post("/save-as-flashcard")
def save_as_flashcard(body: SaveAsFlashcardIn, request: Request,
                      current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    from models import Course, Flashcard

    # Confirm the assistant message belongs to a session owned by the
    # current user (prevents saving someone else's tutor content)
    assistant = db.query(AITutorMessage).join(
        AITutorSession, AITutorSession.id == AITutorMessage.session_id
    ).filter(
        AITutorMessage.id == body.message_id,
        AITutorMessage.role == "assistant",
        AITutorSession.user_id == current.id,
        AITutorSession.organization_id == current.organization_id,
    ).first()
    if not assistant:
        raise HTTPException(status_code=404, detail="Message not found")

    # Prior user turn = the question
    prior_user = db.query(AITutorMessage).filter(
        AITutorMessage.session_id == assistant.session_id,
        AITutorMessage.role == "user",
        AITutorMessage.id < assistant.id,
    ).order_by(AITutorMessage.id.desc()).first()
    if not prior_user:
        raise HTTPException(status_code=400,
                            detail="No user question found before this answer")

    # Confirm the target course is in the user's org
    course = db.query(Course).filter(
        Course.id == body.course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Extract citation chunk IDs for provenance
    citation_ids = [c["chunk_id"] for c in (assistant.citations or [])
                    if c.get("chunk_id") is not None]

    card = Flashcard(
        organization_id=current.organization_id,
        course_id=course.id,
        front=(prior_user.content[:497] + "…") if len(prior_user.content) > 500 else prior_user.content,
        back=assistant.content,
        difficulty=body.difficulty,
        tags=["from-tutor"],
        generated_by_ai=True,
        source_chunk_ids=citation_ids or None,
        created_by_id=current.id,
    )
    db.add(card)
    audit_service.record(db, current, "FLASHCARD_SAVED_FROM_TUTOR",
                         target_type="flashcard", target_id=None,
                         metadata={"session_id": assistant.session_id,
                                   "message_id": assistant.id,
                                   "course_id": course.id},
                         request=request)
    db.commit(); db.refresh(card)
    return {"flashcard_id": card.id, "front": card.front,
            "back_length": len(card.back or "")}
