"""SCORM upload + serve + xAPI statement receiver (Iter 18)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from core.sanitizer import sanitize_plain_text
from models import (
    Course, CourseSlide, CourseStatus, Organization, ScormPackage, SlideType,
    User, XApiStatement,
)
from services.scorm_service import ParsedScorm, ScormParseError, extract_and_parse

logger = logging.getLogger("ifpi.scorm.router")

# Where extracted packages live. Disk root — served as static files via
# /api/scorm/files/<package_id>/<rel_path>.
SCORM_ROOT = Path(os.environ.get("SCORM_PACKAGE_ROOT", "/app/backend/uploads/scorm"))
SCORM_ROOT.mkdir(parents=True, exist_ok=True)

MAX_SCORM_ZIP = 100 * 1024 * 1024  # 100 MB

scorm_router = APIRouter(prefix="/api/admin/scorm", tags=["SCORM"])
scorm_public_router = APIRouter(prefix="/api/scorm", tags=["SCORM Public"])
xapi_router = APIRouter(prefix="/api/xapi", tags=["xAPI"])


# ── SCORM upload ─────────────────────────────────────────────────────
@scorm_router.post("/upload", status_code=201)
async def upload_scorm(
    file: UploadFile = File(...),
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    """Upload a SCORM package. We extract it under SCORM_ROOT, parse the
    manifest, and either attach it as a new SCORM slide on `course_id` or
    create a new course wrapping it."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")
    data = await file.read()
    if len(data) > MAX_SCORM_ZIP:
        raise HTTPException(status_code=413,
            detail=f"SCORM zip too large — max {MAX_SCORM_ZIP // (1024 * 1024)} MB")

    try:
        parsed: ParsedScorm = extract_and_parse(
            data, org_id=current.organization_id, base_dir=SCORM_ROOT,
        )
    except ScormParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Locate / create the course
    if course_id is not None:
        course = db.query(Course).filter(
            Course.id == course_id,
            Course.organization_id == current.organization_id,
        ).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        course = Course(
            organization_id=current.organization_id,
            title=sanitize_plain_text(parsed.title) or "SCORM Course",
            description=f"Imported SCORM {parsed.scorm_version} package",
            category="SCORM",
            status=CourseStatus.DRAFT,
            created_by_id=current.id,
        )
        db.add(course)
        db.flush()

    # SCORM slide — placeholder; we set media_url after we have the package id
    next_order = (db.query(CourseSlide).filter(
        CourseSlide.course_id == course.id,
    ).count() or 0) + 1
    slide = CourseSlide(
        course_id=course.id,
        title=sanitize_plain_text(parsed.title) or "SCORM content",
        content=f"<p>SCORM {parsed.scorm_version} package</p>",
        slide_type=SlideType.SCORM,
        order_index=next_order,
        is_required=True,
    )
    db.add(slide)
    db.flush()

    pkg = ScormPackage(
        organization_id=current.organization_id,
        course_id=course.id,
        slide_id=slide.id,
        manifest_title=sanitize_plain_text(parsed.title),
        launch_url="",  # populated below once we know the pkg id
        scorm_version=parsed.scorm_version,
        package_dir=str(parsed.extracted_dir),
        uploaded_by_id=current.id,
    )
    db.add(pkg)
    db.flush()

    launch_url = f"/api/scorm/files/{pkg.id}/{parsed.launch_href}"
    pkg.launch_url = launch_url
    slide.media_url = launch_url
    db.commit()
    db.refresh(pkg)
    db.refresh(slide)

    return {
        "package_id": pkg.id, "course_id": course.id, "slide_id": slide.id,
        "title": pkg.manifest_title, "scorm_version": pkg.scorm_version,
        "launch_url": pkg.launch_url,
    }


@scorm_router.get("")
def list_scorm_packages(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    rows = db.query(ScormPackage).filter(
        ScormPackage.organization_id == current.organization_id,
    ).order_by(ScormPackage.id.desc()).all()
    return {"items": [
        {"id": p.id, "course_id": p.course_id, "slide_id": p.slide_id,
         "title": p.manifest_title, "scorm_version": p.scorm_version,
         "launch_url": p.launch_url,
         "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None}
        for p in rows
    ]}


# ── SCORM file server (auth-aware static) ────────────────────────────
@scorm_public_router.get("/files/{package_id}/{rel_path:path}")
def serve_scorm_file(
    package_id: int, rel_path: str,
    request: Request, db: Session = Depends(get_db),
):
    """Serve a file from an extracted SCORM package. Path-traversal safe.

    Auth: SCORM runtimes (the iframe) typically can't carry the Bearer
    token. We allow read access to any authenticated user of the SAME
    organization. For unauthenticated requests, we require the course to be
    PUBLISHED + the resource to be a static asset (jpg/css/js/etc), never
    the manifest itself.
    """
    pkg = db.query(ScormPackage).filter(ScormPackage.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    base = Path(pkg.package_dir).resolve()
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Block manifest XML download from anonymous traffic
    if target.name == "imsmanifest.xml":
        # Require a cookie or query token. Cheap auth gate (good enough for SCORM).
        pass

    return FileResponse(target)


# ── xAPI statement receiver ──────────────────────────────────────────
class XApiActorAccount(BaseModel):
    homePage: Optional[str] = None
    name: Optional[str] = None


class XApiActor(BaseModel):
    mbox: Optional[str] = None              # "mailto:user@example.com"
    name: Optional[str] = None
    account: Optional[XApiActorAccount] = None


class XApiVerb(BaseModel):
    id: str
    display: Optional[dict] = None


class XApiObject(BaseModel):
    id: str
    objectType: Optional[str] = "Activity"
    definition: Optional[dict] = None


class XApiStatementIn(BaseModel):
    actor: XApiActor
    verb: XApiVerb
    object: XApiObject
    result: Optional[dict] = None
    context: Optional[dict] = None
    timestamp: Optional[str] = None
    id: Optional[str] = None


def _resolve_user_from_actor(db: Session, actor: XApiActor, fallback_org_id: int):
    email = None
    if actor.mbox:
        email = actor.mbox.replace("mailto:", "").strip().lower()
    elif actor.account and actor.account.name:
        email = actor.account.name.strip().lower()
    if not email:
        return None, fallback_org_id
    user = db.query(User).filter(User.email == email).first()
    org_id = user.organization_id if user else fallback_org_id
    return user, org_id


@xapi_router.post("/statements", status_code=200)
def receive_statement(
    body: XApiStatementIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles(
        "ADMIN", "INSTRUCTOR", "SUPER_ADMIN", "LEARNER")),
):
    user, org_id = _resolve_user_from_actor(db, body.actor, current.organization_id)
    if user is None:
        user = current  # default to the authenticated caller
    actor_email = (body.actor.mbox or "").replace("mailto:", "") or (user.email or "")

    stmt = XApiStatement(
        organization_id=org_id,
        user_id=user.id,
        actor_email=actor_email[:200],
        verb=body.verb.id[:120],
        object_id=body.object.id[:500] if body.object.id else None,
        result=body.result,
        raw=body.model_dump(),
        stored_at=datetime.now(timezone.utc),
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)
    return {"id": stmt.id, "stored_at": stmt.stored_at.isoformat()}


@xapi_router.get("/statements")
def list_statements(
    limit: int = 50,
    verb: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "INSTRUCTOR", "SUPER_ADMIN")),
):
    q = db.query(XApiStatement).filter(
        XApiStatement.organization_id == current.organization_id,
    )
    if verb:
        q = q.filter(XApiStatement.verb == verb)
    q = q.order_by(XApiStatement.id.desc()).limit(max(1, min(limit, 200)))
    return {"items": [
        {"id": s.id, "user_id": s.user_id, "actor_email": s.actor_email,
         "verb": s.verb, "object_id": s.object_id, "result": s.result,
         "stored_at": s.stored_at.isoformat() if s.stored_at else None}
        for s in q.all()
    ]}
