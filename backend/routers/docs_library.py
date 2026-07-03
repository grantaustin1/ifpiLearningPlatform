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

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse

from auth.dependencies import CurrentUser, requires_admin
from services import docs_library_service

router = APIRouter(prefix="/api/admin/docs", tags=["Docs Library"])


@router.get("")
def list_docs(_current: CurrentUser = Depends(requires_admin())):
    """Return catalog of downloadable documents with metadata."""
    return {"documents": docs_library_service.list_manifest()}


@router.get("/{slug}/pdf")
def download_pdf(
    slug: str,
    _current: CurrentUser = Depends(requires_admin()),
):
    """Stream a rendered PDF of the requested document."""
    rendered = docs_library_service.render_pdf(slug)
    if rendered is None:
        raise HTTPException(status_code=404,
                            detail=f"Document {slug!r} not found")
    pdf_bytes, filename = rendered
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{slug}/raw", response_class=PlainTextResponse)
def download_raw(
    slug: str,
    _current: CurrentUser = Depends(requires_admin()),
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
    return PlainTextResponse(
        content=src.read_text(encoding="utf-8"),
        headers={
            "Content-Disposition": f'attachment; filename="{meta["file"]}"',
        },
    )
