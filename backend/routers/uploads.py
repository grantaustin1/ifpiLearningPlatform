"""Uploads router — image upload, cover library, file serving with range support."""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from services.storage_service import StorageError, get_storage


uploads_router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml"}
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]")


@uploads_router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    request: Request = None,
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Accepts logo / signature image. Delegates to the configured storage
    backend (local | s3 | gcs) — mirrors the ERP360 storage abstraction."""
    if file.content_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {file.content_type}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5MB)")
    suffix = Path(file.filename or "upload").suffix.lower() or ".png"
    safe_suffix = _SAFE_NAME.sub("_", suffix)
    key = f"branding/{uuid.uuid4().hex}{safe_suffix}"
    try:
        url = get_storage().save(data, key, content_type=file.content_type)
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"url": url, "key": key, "size": len(data)}


@uploads_router.get("/cover-library")
def cover_library(current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Curated course-cover photo gallery (Iter 43). Files are placed by
    scripts/build_cover_library.py into uploads/covers/library/."""
    lib_dir = Path(__file__).resolve().parents[1] / "uploads" / "covers" / "library"
    items = []
    if lib_dir.is_dir():
        for f in sorted(lib_dir.glob("*.jpg")):
            items.append({
                "url": f"/api/uploads/files/covers/library/{f.name}",
                "label": f.stem.replace("_", " ").title(),
            })
    return items


def _range_response(path: Path, mime: str, range_header: str):
    """Serve a single byte range (RFC 7233) so <video> can seek and browsers
    stop downloading whole files. Returns None if the header is unusable."""
    import re as _re
    m = _re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    size = path.stat().st_size
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:  # suffix range: last N bytes
        start = max(size - int(m.group(2)), 0)
        end = size - 1
    if start >= size:
        return StreamingResponse(
            iter([]), status_code=416,
            headers={"Content-Range": f"bytes */{size}"})
    end = min(end, size - 1)
    length = end - start + 1

    def iter_chunk(chunk=1024 * 256):
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_chunk(), status_code=206, media_type=mime,
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "public, max-age=3600",
        })


@uploads_router.get("/files/{path:path}")
def serve_upload(path: str, request: Request):
    """Serve a previously-uploaded file (local disk or object-store cache).
    Supports HTTP Range requests for video seeking."""
    storage = get_storage()
    suffix = Path(path).suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif",
            ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
            ".m4v": "video/x-m4v", ".ogg": "video/ogg",
            ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
            ".pdf": "application/pdf"}.get(suffix, "application/octet-stream")
    local = storage.local_path(path)
    if local is not None:
        range_header = request.headers.get("range")
        if range_header:
            resp = _range_response(local, mime, range_header)
            if resp is not None:
                return resp
        return FileResponse(local, media_type=mime,
                            headers={"Cache-Control": "public, max-age=3600",
                                     "Accept-Ranges": "bytes"})
    try:
        content = storage.load(path)
    except StorageError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=content, media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )
