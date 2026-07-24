from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import Depends, File, HTTPException, Request, Response, UploadFile

from auth.dependencies import CurrentUser, requires_roles
from services.storage_service import StorageError, get_storage

from . import uploads_router

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


@uploads_router.get("/files/{path:path}")
def serve_upload(path: str):
    """Serve a previously-uploaded file. ONLY meaningful for the `local`
    backend — S3/GCS URLs are public/CDN and bypass this route."""
    storage = get_storage()
    if not storage.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = storage.load(path)
    except StorageError as e:
        raise HTTPException(status_code=404, detail=str(e))
    suffix = Path(path).suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".svg": "image/svg+xml"}.get(suffix, "application/octet-stream")
    return Response(
        content=content, media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )
