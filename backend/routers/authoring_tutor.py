"""Source-grounded tutor + sources CRUD (Iter 23) + Tavily research skeleton (Iter 24).

Endpoints (all staff-only via `requires_staff()`):
  Sources:
   POST   /api/authoring/sources         — upload plain text OR extract from PDF/DOCX
   GET    /api/authoring/sources         — list per org
   DELETE /api/authoring/sources/{id}    — cascade-deletes chunks
   POST   /api/authoring/sources/search  — semantic top-k search
  Tutor:
   POST   /api/authoring/tutor/ask       — grounded Q&A with citations
  Research (Iter 24):
   POST   /api/authoring/research/start  — kick off Tavily deep research
   GET    /api/authoring/research/{id}   — poll AIJob status
"""
from __future__ import annotations

import logging
<<<<<<< HEAD
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List, Optional
=======
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional
>>>>>>> origin/main

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

<<<<<<< HEAD
from auth.dependencies import CurrentUser, requires_admin, requires_staff
=======
from auth.dependencies import CurrentUser, requires_staff
>>>>>>> origin/main
from core.config import settings
from core.database import SessionLocal, get_db
from core.sanitizer import sanitize_plain_text
from models import AIJob, SourceChunk, SourceDocument
from services import embedding_service, tutor_service

logger = logging.getLogger("ifpi.authoring.tutor")

router = APIRouter(prefix="/api/authoring", tags=["AI Authoring"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024   # 25 MB — plenty for a chapter PDF


# ─── Text extraction helpers (reuse across upload types) ─────────────
def _extract_pdf(data: bytes) -> str:
    """Best-effort PDF text extraction. Prefer PyPDF2 if installed (it's a
    transitive dep of reportlab), else return empty and let the caller
    handle it (they can still store raw text via `text` param)."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        try:
            from pypdf import PdfReader   # newer fork
        except ImportError:
            return ""
    try:
        reader = PdfReader(BytesIO(data))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:   # noqa: BLE001
        logger.exception("PDF text extraction failed")
        return ""


def _extract_docx(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        return ""
    try:
        d = docx.Document(BytesIO(data))
        return "\n\n".join(p.text for p in d.paragraphs if p.text.strip())
    except Exception:   # noqa: BLE001
        logger.exception("DOCX text extraction failed")
        return ""


# ─── Sources CRUD ────────────────────────────────────────────────────
def _doc_to_dict(d: SourceDocument) -> dict:
    return {
        "id": d.id, "title": d.title, "source_type": d.source_type,
        "original_url": d.original_url,
        "course_id": d.course_id, "chunk_count": d.chunk_count,
        "embedded_at": d.embedded_at.isoformat() if d.embedded_at else None,
        "uploaded_by_id": d.uploaded_by_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "text_length": len(d.extracted_text or ""),
    }


@router.post("/sources", status_code=201)
async def upload_source(
    file: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    source_type: Optional[str] = Form(None),
    course_id: Optional[int] = Form(None),
    original_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Upload a source. Two modes:
     - Multipart with `file` — .pdf, .docx, .txt, .md
     - Multipart with `text` — paste raw text (source_type=MANUAL/RESEARCH_NOTE)
    Both modes require at least a title.
    """
    extracted_text = (text or "").strip()
    stype = (source_type or "MANUAL").upper()
    resolved_title = (title or "").strip()

    if file:
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413,
                detail=f"File too large — max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        fname = (file.filename or "upload").lower()
        if not resolved_title:
            resolved_title = Path(file.filename or "Untitled").stem.replace("_", " ").title()

        if fname.endswith(".pdf"):
            extracted_text = _extract_pdf(data)
            stype = "PDF"
        elif fname.endswith(".docx"):
            extracted_text = _extract_docx(data)
            stype = "DOCX"
        elif fname.endswith((".txt", ".md")):
            extracted_text = data.decode("utf-8", errors="ignore")
            stype = "MANUAL"
        else:
            raise HTTPException(status_code=400,
                detail="Unsupported file type — use .pdf, .docx, .txt, or .md")

        if not extracted_text.strip():
            raise HTTPException(status_code=422,
                detail="Could not extract any text from this file")

    if not resolved_title:
        raise HTTPException(status_code=400, detail="`title` is required")
    if not extracted_text.strip():
        raise HTTPException(status_code=400,
            detail="Either upload a file OR provide `text`")

    # Sanitize display text but keep the extraction for embedding as-is
    resolved_title = sanitize_plain_text(resolved_title)[:300]

    doc = await embedding_service.ingest_document(
        db,
        organization_id=current.organization_id,
        uploaded_by_id=current.id,
        title=resolved_title,
        text=extracted_text,
        source_type=stype,
        original_url=(original_url or None),
        course_id=course_id,
    )
    return _doc_to_dict(doc)


@router.get("/sources")
def list_sources(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    q = db.query(SourceDocument).filter(
        SourceDocument.organization_id == current.organization_id,
    )
    if course_id is not None:
        q = q.filter(SourceDocument.course_id == course_id)
    rows = q.order_by(SourceDocument.id.desc()).all()
    return {"items": [_doc_to_dict(d) for d in rows]}


@router.delete("/sources/{doc_id}")
def delete_source(
    doc_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    doc = db.query(SourceDocument).filter(
        SourceDocument.id == doc_id,
        SourceDocument.organization_id == current.organization_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Source not found")
    # SQLAlchemy cascade delete on source_chunks via ondelete=CASCADE
    db.query(SourceChunk).filter(SourceChunk.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()
    return {"ok": True, "id": doc_id}


class SearchIn(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    course_id: Optional[int] = None


@router.post("/sources/search")
async def semantic_search(
    body: SearchIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    hits = await embedding_service.semantic_search(
        db, organization_id=current.organization_id,
        query=body.query, top_k=body.top_k, course_id=body.course_id,
    )
    return {"hits": hits}


# ─── Tutor Q&A ───────────────────────────────────────────────────────
class TutorAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    course_id: Optional[int] = None
    top_k: int = Field(5, ge=1, le=10)
    pii_redact: bool = True


@router.post("/tutor/ask")
async def tutor_ask(
    body: TutorAskIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    from services import ai_budget_service
    ai_budget_service.check_budget(db, current.organization_id, estimated_cost_cents=1)

    # Locked policy (b): only ADMIN/SUPER_ADMIN may disable PII redaction.
    if not body.pii_redact:
        if not any(r in ("ADMIN", "SUPER_ADMIN") for r in current.roles):
            raise HTTPException(status_code=403,
                detail="Only ADMIN or SUPER_ADMIN can disable PII redaction")
        from services import audit_service
        audit_service.record(
            db, current, "AI_PII_REDACT_DISABLED",
            target_type="tutor_question", target_id="",
            metadata={"question_preview": body.question[:120]},
        )
        db.commit()

    return await tutor_service.tutor_answer(
        db, organization_id=current.organization_id, user_id=current.id,
        question=body.question, course_id=body.course_id,
        top_k=body.top_k, pii_redact=body.pii_redact,
    )


# ─── Iter 24: Deep research via Tavily (skeleton) ─────────────────────
class ResearchStartIn(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    depth: str = Field("quick", pattern="^(quick|deep)$")
    course_id: Optional[int] = None


def _run_research_job(job_id: int, org_id: int, query: str, depth: str,
                       course_id: Optional[int], user_id: int) -> None:
    """Sync wrapper — spins up its own event loop so FastAPI's BackgroundTasks
    (which runs coroutines in the main loop and sync callables in a worker
    thread) can call this without loop conflicts."""
    import asyncio
    try:
        asyncio.run(_run_research_job_async(job_id, org_id, query, depth,
                                              course_id, user_id))
    except Exception:   # noqa: BLE001
        logger.exception("Research job runner crashed (job_id=%s)", job_id)


async def _run_research_job_async(job_id: int, org_id: int, query: str, depth: str,
                                    course_id: Optional[int], user_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(AIJob).filter(AIJob.id == job_id).first()
        if not job:
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        if not settings.tavily_api_key:
            job.status = "FAILED"
            job.error_log = (
                "TAVILY_API_KEY not set. Add it to backend/.env and restart the "
                "backend to enable deep research. Get a key at https://tavily.com."
            )
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        import httpx
        max_results = 10 if depth == "deep" else 5
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key, "query": query,
                        "max_results": max_results,
                        "search_depth": "advanced" if depth == "deep" else "basic",
                        "include_answer": True, "include_raw_content": True,
                    },
                )
            r.raise_for_status()
            tavily_data = r.json()
        except Exception as e:   # noqa: BLE001
            job.status = "FAILED"
            job.error_log = f"Tavily API error: {e}"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        answer = tavily_data.get("answer") or ""
        results = tavily_data.get("results", [])
        briefing = f"# Research briefing: {query}\n\n{answer}\n\n---\n\n## Sources\n\n"
        for i, res in enumerate(results, 1):
            briefing += (
                f"### [{i}] {res.get('title', 'Untitled')}\n"
                f"<{res.get('url')}>\n\n"
                f"{(res.get('content') or res.get('raw_content') or '')[:1500]}\n\n"
            )

        title = f"Research: {query[:80]}"
        doc = await embedding_service.ingest_document(
            db,
            organization_id=org_id, uploaded_by_id=user_id,
            title=title, text=briefing,
            source_type="RESEARCH_NOTE",
            course_id=course_id,
            metadata={"query": query, "depth": depth,
                      "sources": [r.get("url") for r in results]},
        )

        # Record cost — Tavily is not on the Emergent LLM key; approximate
        # spend per docs.tavily.com pricing (~$0.008/basic, $0.03/advanced).
        try:
            from services import ai_budget_service
            cost_cents = 3 if depth == "deep" else 1
            ai_budget_service.record_spend(
                db, organization_id=org_id, user_id=user_id, job_id=job_id,
                provider="tavily", model=f"search-{depth}",
                cost_cents=cost_cents,
            )
        except Exception:   # noqa: BLE001
            logger.exception("Failed to record tavily spend")

        job.status = "COMPLETED"
        job.output_json = {
            "source_document_id": doc.id, "chunk_count": doc.chunk_count,
            "source_count": len(results),
        }
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:   # noqa: BLE001
        logger.exception("Research job crashed: %s", e)
        try:
            job = db.query(AIJob).filter(AIJob.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_log = f"Unhandled: {e}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/research/start", status_code=202)
def research_start(
    body: ResearchStartIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Kick off a deep research job. Returns immediately with the AIJob id.
    Client polls `GET /research/{id}` for status."""
    if not settings.tavily_api_key:
        # Still create the job so admins can see the failed attempt in
        # their AI-jobs list — but flag it as needing config.
        raise HTTPException(
            status_code=503,
            detail={
                "code": "tavily_key_missing",
                "message": (
                    "Deep research requires a Tavily API key. Add "
                    "TAVILY_API_KEY to backend/.env and restart. Get a "
                    "key at https://tavily.com (free tier: 1000 searches/mo)."
                ),
            },
        )

    from services import ai_budget_service
    est = 8 if body.depth == "deep" else 3   # cents
    ai_budget_service.check_budget(db, current.organization_id, estimated_cost_cents=est)

    job = AIJob(
        organization_id=current.organization_id,
        created_by_id=current.id,
        job_type="DEEP_RESEARCH",
        status="PENDING",
        input_json={"query": body.query, "depth": body.depth,
                    "course_id": body.course_id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background.add_task(
        _run_research_job, job.id, current.organization_id,
        body.query, body.depth, body.course_id, current.id,
    )
    return {"job_id": job.id, "status": job.status}


@router.get("/research/{job_id}")
def research_status(
    job_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    job = db.query(AIJob).filter(
        AIJob.id == job_id,
        AIJob.organization_id == current.organization_id,
        AIJob.job_type == "DEEP_RESEARCH",
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return {
        "id": job.id, "status": job.status,
        "input": job.input_json, "output": job.output_json,
        "error_log": job.error_log,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/research")
def list_research_jobs(
    limit: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """List recent research jobs for the org's history view."""
    jobs = db.query(AIJob).filter(
        AIJob.organization_id == current.organization_id,
        AIJob.job_type == "DEEP_RESEARCH",
    ).order_by(AIJob.id.desc()).limit(min(limit, 100)).all()
    return {
        "items": [
            {
                "id": j.id, "status": j.status,
                "input": j.input_json, "output": j.output_json,
                "error_log": j.error_log,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ],
    }
