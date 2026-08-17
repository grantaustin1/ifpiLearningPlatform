"""Publish the 3 scaffolded module courses + ingest their text for the
AI tutor. Strips the '[DRAFT — micro-video to be added]' marker first.

Usage: python scripts/publish_modules.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from models import Course, CourseSlide, CourseStatus, SourceDocument  # noqa: E402

COURSE_IDS = [295, 296, 297]
MARKER = "<p>[DRAFT — micro-video to be added]</p>"


async def main():
    from services.embedding_service import ingest_document
    db = SessionLocal()
    for cid in COURSE_IDS:
        c = db.query(Course).filter(Course.id == cid).first()
        if not c:
            print(f"course #{cid} missing — skipped")
            continue
        slides = db.query(CourseSlide).filter(
            CourseSlide.course_id == cid).order_by(
            CourseSlide.order_index).all()
        stripped = 0
        for s in slides:
            if s.content and MARKER in s.content:
                s.content = s.content.replace(MARKER, "")
                stripped += 1
        c.status = CourseStatus.PUBLISHED
        db.commit()
        print(f"published #{cid} {c.title} ({len(slides)} slides, "
              f"{stripped} markers stripped)")

        doc_title = f"{c.title} — slide transcripts"
        exists = db.query(SourceDocument).filter(
            SourceDocument.organization_id == c.organization_id,
            SourceDocument.title == doc_title).first()
        if exists:
            print(f"  RAG doc already exists (#{exists.id})")
            continue
        import re
        text_parts = []
        for s in slides:
            body = re.sub(r"<[^>]+>", " ", s.content or "")
            text_parts.append(f"{s.title}\n{' '.join(body.split())}")
        doc = await ingest_document(
            db, organization_id=c.organization_id, uploaded_by_id=1,
            title=doc_title, text="\n\n".join(text_parts),
            source_type="COURSE_TRANSCRIPT", course_id=c.id)
        print(f"  ingested RAG doc #{doc.id} ({doc.chunk_count} chunks)")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
