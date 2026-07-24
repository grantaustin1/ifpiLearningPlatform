"""AI Authoring Suite — RAG corpus, jobs, ledger, flashcards, tutor sessions.

**Iter 34 (P2 option a — pgvector-ready)**
`SourceChunk.embedding` is defined via `_embedding_column()` which
returns:
  - `Vector(1536)` if `pgvector` is installed AND `USE_PGVECTOR=true`
  - `JSON`         otherwise (SQLite / dev / no-op fallback)

This lets us ship a single codebase that transparently switches to
pgvector the moment the operator flips the env flag against a Postgres
instance with the `vector` extension installed. Zero code changes needed
at cutover. See `services/embedding_service.py::semantic_search` for
the matching query-time branch.
"""
from __future__ import annotations

import os

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)

from core.database import Base
from ._common import _utcnow


def _embedding_column():
    """Return the right column type for storing chunk embeddings.

    - When `USE_PGVECTOR=true` **and** the `pgvector` python package is
      importable, we use pgvector's native `Vector(1536)` type which
      unlocks `<=>` cosine-distance queries + HNSW/IVFFlat indexes.
    - Otherwise, fall back to a plain `JSON` list-of-floats column. This
      keeps SQLite dev + prod-without-pgvector working identically.
    """
    if os.environ.get("USE_PGVECTOR", "").lower() in ("1", "true", "yes"):
        try:
            from pgvector.sqlalchemy import Vector  # type: ignore
            return Column(Vector(1536))
        except ImportError:  # pragma: no cover — safety net
            pass
    return Column(JSON)


class SourceDocument(Base):
    """Per-org reference material — PDFs, DOCXs, URLs scraped by deep-research.
    Used as the retrieval corpus for the source-grounded AI tutor. Full-text
    plus per-chunk embeddings (see `SourceChunk`) enable semantic search."""
    __tablename__ = "source_documents"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    title = Column(String(300), nullable=False)
    source_type = Column(String(20), nullable=False)     # PDF | DOCX | URL | RESEARCH_NOTE | MANUAL
    original_url = Column(String(800))                    # populated when scraped from URL
    storage_key = Column(String(400))                     # storage_service key of raw file
    extracted_text = Column(Text)                         # plain-text — the RAG input
    metadata_json = Column(JSON)                          # {authors, published_date, checksum, page_count}
    chunk_count = Column(Integer, default=0, nullable=False)
    embedded_at = Column(DateTime)                        # nullable — set once embeddings finished
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class SourceChunk(Base):
    """Retrieval-ready ~800-token chunk of a SourceDocument.

    See module docstring — `embedding` column type is either
    `pgvector.Vector(1536)` (prod-ready) or `JSON` (dev fallback).
    """
    __tablename__ = "source_chunks"
    __table_args__ = (Index("ix_chunk_doc_ord", "document_id", "chunk_index"),)
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("source_documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = _embedding_column()                       # list[float] 1536-dim (OpenAI ada-2)
    token_count = Column(Integer)


class AIJob(Base):
    """Async LLM/media dispatch — mirrors the ImportJob pattern (Iter 16)."""
    __tablename__ = "ai_jobs"
    __table_args__ = (Index("ix_ai_jobs_org_status", "organization_id", "status"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    job_type = Column(String(40), nullable=False, index=True)
    # TUTOR_ANSWER | DEEP_RESEARCH | AUTO_QUIZ | FLASHCARDS | VIDEO_OVERVIEW
    # TTS_NARRATION | MIND_MAP | INFOGRAPHIC | PPTX_EXPORT
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    input_json = Column(JSON)
    output_json = Column(JSON)
    artefact_url = Column(String(600))
    cost_cents = Column(Integer, default=0, nullable=False)
    error_log = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class AIUsageLedger(Base):
    """Per-call cost tracking. Aggregated per (org, billing_month) by
    services/ai_budget_service to enforce Organization.ai_monthly_budget_cents.
    """
    __tablename__ = "ai_usage_ledger"
    __table_args__ = (Index("ix_ai_usage_org_month", "organization_id", "billing_month"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("ai_jobs.id"), nullable=True)
    provider = Column(String(30), nullable=False)         # claude | openai | gemini | sora | tavily
    model = Column(String(60))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_cents = Column(Integer, default=0, nullable=False)
    billing_month = Column(String(7), nullable=False)     # "2026-02"
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class Flashcard(Base):
    """One AI-generated flashcard. Belongs to a course (org-scoped via that
    course). `source_chunk_ids` records provenance so we can show citations
    on the review UI + guarantee no hallucinated cards enter the pack."""
    __tablename__ = "flashcards"
    __table_args__ = (
        Index("ix_flashcards_org_course", "organization_id", "course_id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id"), nullable=True)
    front = Column(String(500), nullable=False)          # question / prompt
    back = Column(Text, nullable=False)                    # answer
    hint = Column(String(300))
    difficulty = Column(Integer, default=2, nullable=False)  # 1-easy .. 5-hard
    tags = Column(JSON)                                     # list[str]
    generated_by_ai = Column(Boolean, default=True, nullable=False)
    source_chunk_ids = Column(JSON)                        # list[int] — provenance
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class FlashcardReview(Base):
    """Learner-side SM-2 spaced-repetition state. One row per (user, card)."""
    __tablename__ = "flashcard_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "flashcard_id", name="uq_review_user_card"),
        Index("ix_reviews_user_next", "user_id", "next_review_at"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    ease_factor = Column(Float, default=2.5, nullable=False)   # SM-2 EF
    interval_days = Column(Integer, default=0, nullable=False)  # days until next review
    repetitions = Column(Integer, default=0, nullable=False)   # consecutive successful reps
    next_review_at = Column(DateTime, nullable=False)
    last_quality = Column(Integer)                              # last 0-5 rating
    last_reviewed_at = Column(DateTime)
    review_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class AITutorSession(Base):
    """One conversation with the AI tutor. Keyed to (user, course) —
    persisted so learners can resume mid-chat."""
    __tablename__ = "ai_tutor_sessions"
    __table_args__ = (
        Index("ix_tutor_session_user_course",
              "user_id", "course_id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False,
                     index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"),
                       nullable=True, index=True)
    title = Column(String(200), nullable=False, default="New chat")
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    last_message_at = Column(DateTime, default=_utcnow, nullable=False)


class AITutorMessage(Base):
    """One turn (either user or assistant). Assistant turns carry a JSON
    `citations` list: `[{chunk_id, document_id, document_title, snippet, score}]`.
    """
    __tablename__ = "ai_tutor_messages"
    __table_args__ = (
        Index("ix_tutor_msg_session", "session_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer,
                        ForeignKey("ai_tutor_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    role = Column(String(12), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)    # list[dict] on assistant turns
    tokens_prompt = Column(Integer, nullable=True)
    tokens_completion = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
