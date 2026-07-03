"""Docs Library router (Iter 30e).

Exposes the IFPI manuals for in-app download from the Settings →
Documents tab. Admin+ only — the manuals reference internal
implementation details we don't publish to learners.

Endpoints
---------
- `GET /api/admin/docs`              — manifest (list of downloadable docs)
- `GET /api/admin/docs/{slug}/pdf`   — streamed PDF download
- `GET /api/admin/docs/{slug}/raw`   — raw markdown (for advanced users
  who want to import into their own doc system)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from services import audit_service, docs_library_service

router = APIRouter(prefix="/api/admin/docs", tags=["Docs Library"])


@router.get("")
def list_docs(_current: CurrentUser = Depends(requires_admin())):
    """Return catalog of downloadable documents with metadata."""
    return {"documents": docs_library_service.list_manifest()}


@router.get("/{slug}/pdf")
def download_pdf(
    slug: str,
    request: Request,
    preview: bool = False,
    current: CurrentUser = Depends(requires_admin()),
    db: Session = Depends(get_db),
):
    """Stream a rendered PDF of the requested document.

    ``preview=true`` marks the audit entry as an inline preview (still
    logged so we know which docs people skim). Without the flag we treat
    it as a true download."""
    rendered = docs_library_service.render_pdf(slug)
    if rendered is None:
        raise HTTPException(status_code=404,
                            detail=f"Document {slug!r} not found")
    pdf_bytes, filename = rendered
    audit_service.record(
        db, current,
        "DOC_PREVIEWED" if preview else "DOC_DOWNLOADED",
        target_type="doc",
        target_id=slug,
        metadata={"format": "pdf", "bytes": len(pdf_bytes)},
        request=request,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            # inline lets the browser render in an iframe/embed; attachment
            # forces a Save-As dialog. `preview` toggles between them.
            "Content-Disposition": (
                f'{"inline" if preview else "attachment"}; filename="{filename}"'
            ),
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{slug}/raw", response_class=PlainTextResponse)
def download_raw(
    slug: str,
    request: Request,
    current: CurrentUser = Depends(requires_admin()),
    db: Session = Depends(get_db),
):
    """Return the raw markdown source (with AUTO-BLOCK markers)."""
    meta = docs_library_service.CATALOG.get(slug)
    if not meta:
        raise HTTPException(status_code=404,
                            detail=f"Document {slug!r} not found")
    src = docs_library_service.DOCS_ROOT / meta["file"]
    if not src.exists():
        raise HTTPException(status_code=404,
                            detail="Source file missing on server")
    body = src.read_text(encoding="utf-8")
    audit_service.record(
        db, current, "DOC_DOWNLOADED",
        target_type="doc", target_id=slug,
        metadata={"format": "markdown", "bytes": len(body)},
        request=request,
    )
    return PlainTextResponse(
        content=body,
        headers={
            "Content-Disposition": f'attachment; filename="{meta["file"]}"',
        },
    )
