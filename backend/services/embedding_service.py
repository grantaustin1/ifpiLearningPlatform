"""Embedding + retrieval service for the source-grounded AI tutor (Iter 23).

Design goals:
 - Keep it dependency-light. No pgvector, no numpy — pure-Python cosine over
   JSON-stored embeddings. Fine up to ~10k chunks/org (our design ceiling).
 - Embeddings come from Emergent LLM Key via `emergentintegrations`. Cost is
   recorded in `AIUsageLedger` so every dispatch counts against the org's
   monthly budget.

Chunker uses a simple paragraph-based split with a soft 800-token target.
Not tokenizer-perfect but good enough — tutor answers still cite chunk_ids
and the LLM is tolerant to fuzzy boundaries.
"""
from __future__ import annotations

import logging
import math
import os
import re
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from models import SourceChunk, SourceDocument

logger = logging.getLogger("ifpi.embeddings")

# Soft chunk sizing — aim for ~800 tokens per chunk (≈3200 chars in English).
_CHUNK_CHAR_TARGET = 3200
_CHUNK_CHAR_MIN = 500
_CHUNK_CHAR_MAX = 4200


def chunk_text(text: str) -> List[str]:
    """Split `text` into ~800-token chunks along paragraph boundaries.
    Merges tiny paragraphs and hard-splits paragraphs that exceed the max."""
    if not text:
        return []
    text = re.sub(r"\r\n?", "\n", text).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]

    chunks: List[str] = []
    buffer = ""
    for p in paragraphs:
        # Paragraph itself is too big → hard-split on sentence boundaries
        if len(p) > _CHUNK_CHAR_MAX:
            if buffer:
                chunks.append(buffer.strip()); buffer = ""
            sentences = re.split(r"(?<=[.!?])\s+", p)
            sb = ""
            for s in sentences:
                if len(sb) + len(s) + 1 > _CHUNK_CHAR_MAX:
                    if sb:
                        chunks.append(sb.strip()); sb = ""
                sb += s + " "
            if sb.strip():
                chunks.append(sb.strip())
            continue

        # Regular case — accumulate until we hit the target
        if len(buffer) + len(p) + 2 > _CHUNK_CHAR_TARGET and len(buffer) >= _CHUNK_CHAR_MIN:
            chunks.append(buffer.strip())
            buffer = p
        else:
            buffer = f"{buffer}\n\n{p}" if buffer else p

    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch-embed a list of strings via the Emergent LLM proxy.
    Returns one vector per input. Raises 503 if the key isn't configured.
    """
    from fastapi import HTTPException

    if not texts:
        return []
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
            detail="Tutor requires EMERGENT_LLM_KEY — set it in backend/.env")

    # The Emergent LLM proxy is OpenAI-compatible; embeddings live at
    # /llm/openai/v1/embeddings on the same host that LlmChat uses.
    from emergentintegrations.llm.utils import get_integration_proxy_url
    import httpx

    base = get_integration_proxy_url().rstrip("/")
    url = f"{base}/llm/openai/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.emergent_llm_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(url, headers=headers, json={
            "model": settings.embedding_model, "input": texts,
        })
    if r.status_code != 200:
        logger.error("Embedding call failed: %s %s", r.status_code, r.text[:400])
        raise HTTPException(
            status_code=502,
            detail=f"Embedding provider returned {r.status_code}",
        )
    data = r.json().get("data", [])
    # Preserve request order (OpenAI returns items with `index`)
    data_sorted = sorted(data, key=lambda d: d.get("index", 0))
    return [d.get("embedding", []) for d in data_sorted]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure-python cosine. Returns 0 on any mismatch/empty input."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def ingest_document(
    db: Session, *,
    organization_id: int,
    uploaded_by_id: int,
    title: str,
    text: str,
    source_type: str = "MANUAL",
    original_url: Optional[str] = None,
    storage_key: Optional[str] = None,
    course_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> SourceDocument:
    """Create a SourceDocument + chunk + embed + persist. One-shot.

    Caller is responsible for extracting `text` from whatever raw file was
    uploaded (PDF/DOCX/URL). This function only handles chunking, embedding,
    and DB writes.
    """
    from datetime import datetime, timezone

    doc = SourceDocument(
        organization_id=organization_id,
        course_id=course_id,
        title=title,
        source_type=source_type,
        original_url=original_url,
        storage_key=storage_key,
        extracted_text=text,
        metadata_json=metadata or {},
        chunk_count=0,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(doc)
    db.flush()

    chunks = chunk_text(text)
    if not chunks:
        db.commit()
        return doc

    vectors = await embed_texts(chunks)
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        db.add(SourceChunk(
            document_id=doc.id,
            chunk_index=idx,
            text=chunk,
            embedding=vec,
            token_count=max(1, len(chunk) // 4),   # rough token estimate
        ))
    doc.chunk_count = len(chunks)
    doc.embedded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    logger.info("Ingested doc id=%d chunks=%d org=%d", doc.id, len(chunks), organization_id)
    return doc


def _use_pgvector() -> bool:
    """True when the operator has flipped USE_PGVECTOR=true AND the
    `pgvector` package is installed. Read at each call so tests can
    monkey-patch os.environ.
    """
    if os.environ.get("USE_PGVECTOR", "").lower() not in ("1", "true", "yes"):
        return False
    try:
        import pgvector  # noqa: F401
        return True
    except ImportError:
        return False


async def semantic_search(
    db: Session, *,
    organization_id: int,
    query: str,
    top_k: int = 5,
    course_id: Optional[int] = None,
) -> List[dict]:
    """Return the top-k most-similar chunks for `query`, scoped to org.

    Result: list of `{chunk_id, document_id, document_title, chunk_index,
    text, score}` sorted by score desc.

    **Iter 34 (P2 option a):** When `USE_PGVECTOR=true` we push the ANN
    search down into Postgres via the `<=>` cosine-distance operator,
    which uses an HNSW index (see Alembic `20260206_add_pgvector.py`).
    Otherwise we fall back to fetching all chunks + a Python-side
    cosine loop — fine at MVP scale (<5000 chunks/org).
    """
    if not query.strip():
        return []
    q_vec_list = await embed_texts([query])
    if not q_vec_list:
        return []
    q_vec = q_vec_list[0]

    # ── Fast path: pgvector `<=>` cosine distance ──────────────────────
    if _use_pgvector():
        try:
            from sqlalchemy import text as _sqltext  # local — avoid top-level dep
            # Cast to a Postgres array literal via SQLAlchemy bindparam.
            # Cosine DISTANCE = 1 - cosine SIMILARITY, so score = 1 - dist.
            course_clause = "AND sd.course_id = :cid" if course_id is not None else ""
            sql = f"""
                SELECT sc.id, sc.document_id, sd.title, sc.chunk_index,
                       sc.text, 1 - (sc.embedding <=> :qvec) AS score
                  FROM source_chunks sc
                  JOIN source_documents sd ON sc.document_id = sd.id
                 WHERE sd.organization_id = :org
                   {course_clause}
              ORDER BY sc.embedding <=> :qvec
                 LIMIT :k
            """
            params = {"qvec": q_vec, "org": organization_id, "k": top_k}
            if course_id is not None:
                params["cid"] = course_id
            rows = db.execute(_sqltext(sql), params).all()
            return [
                {"chunk_id": r[0], "document_id": r[1],
                 "document_title": r[2], "chunk_index": r[3],
                 "text": r[4], "score": round(float(r[5]), 4)}
                for r in rows if r[5] > 0.05
            ]
        except Exception:  # noqa: BLE001 — degrade to Python path on any drift
            pass

    # ── Fallback: Python-side cosine over org corpus ───────────────────
    q = db.query(SourceChunk, SourceDocument).join(
        SourceDocument, SourceChunk.document_id == SourceDocument.id,
    ).filter(SourceDocument.organization_id == organization_id)
    if course_id is not None:
        q = q.filter(SourceDocument.course_id == course_id)
    rows = q.all()

    scored = []
    for chunk, doc in rows:
        score = cosine_similarity(q_vec, chunk.embedding or [])
        scored.append((score, chunk, doc))
    scored.sort(key=lambda r: r[0], reverse=True)

    return [
        {
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "document_title": doc.title,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "score": round(score, 4),
        }
        for score, chunk, doc in scored[:top_k] if score > 0.05
    ]
