"""Bulk content migration — extended uploads, ImportJob tracking,
and a background-task trigger that delegates to scripts/bulk_import.py.

All endpoints require ADMIN / SUPER_ADMIN.
"""
from __future__ import annotations

import json
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import SessionLocal, get_db
from models import (
    Course, CourseSlide, ImportJob, Organization, SlideType,
)
from services.storage_service import StorageError, get_storage

logger = logging.getLogger("ifpi.imports")

# ─────────────────────────────────────────────────────────────────────
# 1) Extended uploads — video / audio / PDF + bulk
# ─────────────────────────────────────────────────────────────────────
media_router = APIRouter(prefix="/api/uploads", tags=["Uploads Extended"])

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]")

# Size caps per category (bytes)
MAX_SIZE = {
    "image": 5 * 1024 * 1024,
    "video": 500 * 1024 * 1024,
    "audio": 50 * 1024 * 1024,
    "pdf": 20 * 1024 * 1024,
}

ALLOWED_MIMES = {
    # image
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml", "image/gif",
    # video
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    # audio
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp3", "audio/x-wav",
    # docs
    "application/pdf",
}


def _category(mime: str) -> str:
    if mime.startswith("image/"): return "image"
    if mime.startswith("video/"): return "video"
    if mime.startswith("audio/"): return "audio"
    if mime == "application/pdf": return "pdf"
    return "other"


def _slide_type(mime: str) -> SlideType:
    cat = _category(mime)
    return {
        "image": SlideType.IMAGE, "video": SlideType.VIDEO,
        "audio": SlideType.AUDIO, "pdf": SlideType.PDF,
    }[cat]


async def _store_one(file: UploadFile, org_id: int) -> dict:
    if not file.content_type or file.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400,
            detail=f"Unsupported MIME type: {file.content_type}")
    data = await file.read()
    cat = _category(file.content_type)
    if len(data) > MAX_SIZE[cat]:
        raise HTTPException(status_code=413,
            detail=f"File too large — max {MAX_SIZE[cat] // (1024*1024)} MB for {cat}")
    suffix = Path(file.filename or "upload").suffix.lower() or ".bin"
    safe_suffix = _SAFE_NAME.sub("_", suffix)
    key = f"media/{org_id}/{uuid.uuid4().hex}{safe_suffix}"
    try:
        url = get_storage().save(data, key, content_type=file.content_type)
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"url": url, "key": key, "size": len(data),
            "mime_type": file.content_type, "category": cat,
            "filename": file.filename}


@media_router.post("/media")
async def upload_media(
    file: UploadFile = File(...),
    course_id: Optional[int] = None,
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
    db: Session = Depends(get_db),
):
    """Single-file upload for video/audio/PDF/image. If `course_id` is set,
    auto-creates a `CourseSlide` with the right `slide_type` + `media_url`."""
    result = await _store_one(file, current.organization_id)

    if course_id is not None:
        course = db.query(Course).filter(
            Course.id == course_id,
            Course.organization_id == current.organization_id,
        ).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        next_order = (db.query(CourseSlide).filter(
            CourseSlide.course_id == course_id,
        ).count() or 0) + 1
        from core.sanitizer import sanitize_plain_text
        title = sanitize_plain_text(
            Path(result["filename"] or "Slide").stem.replace("-", " ").replace("_", " ").title()
        ) or "Slide"
        slide = CourseSlide(
            course_id=course_id,
            title=title,
            content=f"<p>{title}</p>",
            slide_type=_slide_type(result["mime_type"]),
            media_url=result["url"],
            order_index=next_order,
            is_required=True,
        )
        db.add(slide)
        db.commit()
        db.refresh(slide)
        result["slide_id"] = slide.id

    return result


@media_router.post("/bulk-media")
async def upload_bulk_media(
    files: List[UploadFile] = File(...),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    """Multi-file upload. Each file is independently stored. Failed files
    are reported in `errors[]` so partial uploads don't take down the batch."""
    uploaded, errors = [], []
    for f in files:
        try:
            uploaded.append(await _store_one(f, current.organization_id))
        except HTTPException as e:
            errors.append({"filename": f.filename, "error": e.detail})
        except Exception as e:  # noqa: BLE001
            errors.append({"filename": f.filename, "error": str(e)})
    return {"uploaded": len(uploaded), "failed": len(errors),
            "results": uploaded, "errors": errors}


# ─────────────────────────────────────────────────────────────────────
# 2) ImportJob CRUD + background trigger
# ─────────────────────────────────────────────────────────────────────
jobs_router = APIRouter(prefix="/api/admin/imports", tags=["Import Jobs"])


class ImportRunIn(BaseModel):
    source_path: str = Field(min_length=1, max_length=500)
    job_type: str = Field(default="FULL_MIGRATION", max_length=50)
    publish_on_import: bool = False


def _job_to_dict(j: ImportJob) -> dict:
    return {
        "id": j.id, "job_type": j.job_type, "status": j.status,
        "source_path": j.source_path,
        "total_items": j.total_items, "processed_items": j.processed_items,
        "failed_items": j.failed_items,
        "percent": round(j.processed_items / j.total_items * 100, 1)
                   if j.total_items else 0,
        "results": j.results, "error_log": j.error_log,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
    }


@jobs_router.get("")
def list_jobs(limit: int = 25,
              db: Session = Depends(get_db),
              current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(ImportJob).filter(
        ImportJob.organization_id == current.organization_id,
    ).order_by(ImportJob.id.desc()).limit(max(1, min(limit, 100))).all()
    return {"items": [_job_to_dict(j) for j in rows]}


@jobs_router.get("/{job_id}")
def get_job(job_id: int,
            db: Session = Depends(get_db),
            current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    j = db.query(ImportJob).filter(
        ImportJob.id == job_id,
        ImportJob.organization_id == current.organization_id,
    ).first()
    if not j:
        raise HTTPException(status_code=404, detail="Import job not found")
    return _job_to_dict(j)


@jobs_router.post("/{job_id}/rollback")
def rollback_import(job_id: int, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Undo an import job — deletes every course / learning path it created.
    Only works on COMPLETED or PARTIAL jobs and only within the same org.

    The results JSON captured at import time tells us exactly which rows
    were created. We don't touch rows that pre-existed and were updated
    (idempotent imports can't tell the two apart safely), so this is
    conservative: only rows whose IDs appear in `results.courses[].id` /
    `results.paths[].id` are deleted.
    """
    from models import Course, LearningPath, LearningPathItem
    j = db.query(ImportJob).filter(
        ImportJob.id == job_id,
        ImportJob.organization_id == current.organization_id,
    ).first()
    if not j:
        raise HTTPException(status_code=404, detail="Import job not found")
    if j.status not in ("COMPLETED", "PARTIAL"):
        raise HTTPException(status_code=400,
            detail=f"Cannot rollback a job in status {j.status}")

    results = j.results or {}
    deleted_courses, deleted_paths = 0, 0

    for c in results.get("courses", []):
        cid = c.get("id")
        if not cid:
            continue
        row = db.query(Course).filter(
            Course.id == cid,
            Course.organization_id == current.organization_id,
        ).first()
        if row:
            db.delete(row)
            deleted_courses += 1

    for p in results.get("paths", []):
        pid = p.get("id")
        if not pid:
            continue
        # Wipe items first to dodge FK constraints on dialects without cascades
        db.query(LearningPathItem).filter(LearningPathItem.path_id == pid).delete()
        row = db.query(LearningPath).filter(
            LearningPath.id == pid,
            LearningPath.organization_id == current.organization_id,
        ).first()
        if row:
            db.delete(row)
            deleted_paths += 1

    j.status = "ROLLED_BACK"
    j.error_log = (
        f"{(j.error_log or '').strip()}\nRolled back by user {current.id} at "
        f"{datetime.now(timezone.utc).isoformat()} — "
        f"deleted {deleted_courses} courses, {deleted_paths} paths."
    ).strip()
    db.commit()

    from services import audit_service
    audit_service.record(
        db, current, "IMPORT_JOB_ROLLED_BACK",
        target_type="import_job", target_id=str(j.id),
        metadata={"deleted_courses": deleted_courses,
                  "deleted_paths": deleted_paths},
    )
    db.commit()

    return {
        "ok": True, "job_id": j.id,
        "deleted_courses": deleted_courses,
        "deleted_paths": deleted_paths,
    }



@jobs_router.post("/{job_id}/retry", status_code=202)
def retry_import(job_id: int, background_tasks: BackgroundTasks,
                 db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Re-run a FAILED / PARTIAL import against the same staging directory —
    no need to re-upload the ZIP as long as the extracted tree is still on disk."""
    j = db.query(ImportJob).filter(
        ImportJob.id == job_id,
        ImportJob.organization_id == current.organization_id,
    ).first()
    if not j:
        raise HTTPException(status_code=404, detail="Import job not found")
    if j.status not in ("FAILED", "PARTIAL"):
        raise HTTPException(status_code=400,
            detail=f"Only failed or partial imports can be retried (this one is {j.status})")
    src = Path(j.source_path or "")
    if not src.exists() or not src.is_dir():
        raise HTTPException(status_code=410,
            detail="The uploaded files are no longer on the server — please upload the ZIP again")

    new_job = ImportJob(
        organization_id=current.organization_id,
        created_by_id=current.id,
        job_type=j.job_type or "FULL_MIGRATION",
        source_path=str(src),
        status="PENDING",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    from services import audit_service
    audit_service.record(
        db, current, "IMPORT_JOB_RETRIED",
        target_type="import_job", target_id=str(new_job.id),
        metadata={"retried_from_job_id": j.id, "source_path": str(src)},
    )
    db.commit()

    background_tasks.add_task(
        _run_import_in_bg, new_job.id, current.organization_id, str(src), False,
    )
    return _job_to_dict(new_job)


def _run_import_in_bg(job_id: int, org_id: int, source_path: str,
                      publish_on_import: bool) -> None:
    """Background task — opens its own DB session so it doesn't borrow
    the request session that will close once we return."""
    from scripts.bulk_import import run_import_for_job
    with SessionLocal() as db:
        try:
            run_import_for_job(db, job_id=job_id, org_id=org_id,
                               source_path=source_path,
                               publish_on_import=publish_on_import)
        except Exception as e:
            logger.exception("Background import crashed: %s", e)
            job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_log = (job.error_log or "") + "\n" + traceback.format_exc()
                job.completed_at = datetime.now(timezone.utc)
                db.commit()


@jobs_router.post("/run", status_code=202)
def run_import(body: ImportRunIn, background_tasks: BackgroundTasks,
               db: Session = Depends(get_db),
               current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Kick off a bulk import. Returns immediately with the new ImportJob row;
    progress is reported via GET /api/admin/imports/{id}.

    `source_path` MUST be a server-side absolute path (the admin uploads
    the content tree out-of-band — SCP, mounted volume, etc.). We validate
    the path exists before scheduling so admins get instant feedback.
    """
    org = db.query(Organization).filter(
        Organization.id == current.organization_id,
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    src = Path(body.source_path)
    if not src.exists():
        raise HTTPException(status_code=400,
            detail=f"source_path does not exist on the server: {body.source_path}")
    if not src.is_dir():
        raise HTTPException(status_code=400,
            detail="source_path must be a directory")

    job = ImportJob(
        organization_id=org.id,
        created_by_id=current.id,
        job_type=body.job_type or "FULL_MIGRATION",
        source_path=str(src),
        status="PENDING",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Audit row — admin triggered import
    from services import audit_service
    audit_service.record(
        db, current, "IMPORT_JOB_STARTED",
        target_type="import_job", target_id=str(job.id),
        metadata={"source_path": str(src), "job_type": job.job_type,
                  "publish_on_import": body.publish_on_import},
    )
    db.commit()

    background_tasks.add_task(
        _run_import_in_bg, job.id, org.id, str(src), body.publish_on_import,
    )
    return _job_to_dict(job)



# ─────────────────────────────────────────────────────────────────────
# 3) Drag-and-drop ZIP upload — extract into staging, then run import
# ─────────────────────────────────────────────────────────────────────
import shutil
import tempfile
import zipfile

# Hard cap on uploaded ZIP size (defensive — bigger trees should be SCP'd in)
MAX_ZIP_SIZE = 200 * 1024 * 1024  # 200 MB
# Staging root for extracted content. Lives outside the storage backend
# on purpose — these are transient working dirs the importer consumes.
STAGING_ROOT = Path(tempfile.gettempdir()) / "ifpi_import_staging"


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> int:
    """Path-traversal-safe extraction. Returns extracted file count."""
    dest = dest.resolve()
    count = 0
    for member in zf.infolist():
        # Reject absolute paths and ".." escapes
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(dest)):
            raise HTTPException(status_code=400,
                detail=f"ZIP contains unsafe path: {member.filename}")
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        count += 1
    return count


@jobs_router.post("/upload-zip", status_code=202)
async def upload_zip_and_run(
    file: UploadFile = File(...),
    publish_on_import: bool = False,
    job_type: str = "FULL_MIGRATION",
    background_tasks: BackgroundTasks = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Drag-and-drop a content-tree ZIP. We extract it to a temp staging
    directory and immediately kick off a bulk-import job pointing at the
    extracted root. The frontend `ImportsPage` polls for progress."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    data = await file.read()
    if len(data) > MAX_ZIP_SIZE:
        raise HTTPException(status_code=413,
            detail=f"ZIP too large — max {MAX_ZIP_SIZE // (1024 * 1024)} MB")

    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    extract_dir = STAGING_ROOT / f"{current.organization_id}_{uuid.uuid4().hex[:10]}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            extracted = _safe_extract_zip(zf, extract_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Not a valid ZIP archive")

    if extracted == 0:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="ZIP archive is empty")

    # If the ZIP wraps the content under a single top-level dir (the common
    # case when you right-click → "Compress" on macOS / Finder), unwrap it
    # so the importer sees the expected `courses/` / `paths/` structure.
    # Never unwrap when that single dir IS the content root (`courses`/`paths`).
    entries = [p for p in extract_dir.iterdir() if not p.name.startswith(".")]
    root_dir = (entries[0]
                if len(entries) == 1 and entries[0].is_dir()
                and entries[0].name not in ("courses", "paths")
                else extract_dir)

    org = db.query(Organization).filter(
        Organization.id == current.organization_id,
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")

    job = ImportJob(
        organization_id=org.id,
        created_by_id=current.id,
        job_type=job_type or "FULL_MIGRATION",
        source_path=str(root_dir),
        status="PENDING",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from services import audit_service
    audit_service.record(
        db, current, "IMPORT_JOB_STARTED",
        target_type="import_job", target_id=str(job.id),
        metadata={"source_path": str(root_dir), "job_type": job.job_type,
                  "publish_on_import": publish_on_import,
                  "upload_filename": file.filename,
                  "upload_bytes": len(data), "files_extracted": extracted},
    )
    db.commit()

    if background_tasks is not None:
        background_tasks.add_task(
            _run_import_in_bg, job.id, org.id, str(root_dir), publish_on_import,
        )
    return _job_to_dict(job)


# ─────────────────────────────────────────────────────────────────────
# 4) Storage backend diagnostics (admin-only)
# ─────────────────────────────────────────────────────────────────────
from core.config import settings as _settings

storage_router = APIRouter(prefix="/api/admin/storage", tags=["Storage"])


@storage_router.get("/info")
def storage_info(
    _current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Return the currently active storage backend + a probe result so admins
    can confirm a config flip (e.g. STORAGE_BACKEND=s3) actually took effect.
    No secrets returned — only what's safe to display."""
    backend = (_settings.storage_backend or "local").lower()
    info: dict = {"backend": backend}
    if backend == "s3":
        info["bucket"] = _settings.s3_bucket
        info["region"] = _settings.s3_region
    elif backend == "gcs":
        info["bucket"] = _settings.gcs_bucket
        info["project"] = _settings.gcs_project
    else:
        info["path"] = _settings.storage_path

    # Live probe — write & delete a 1-byte file to confirm credentials work.
    probe_key = f"_probe/{uuid.uuid4().hex}.tmp"
    try:
        store = get_storage()
        store.save(b"x", probe_key, content_type="application/octet-stream")
        ok = store.exists(probe_key)
        store.delete(probe_key)
        info["probe"] = {"ok": bool(ok)}
    except Exception as e:  # noqa: BLE001
        info["probe"] = {"ok": False, "error": str(e)}
    return info
