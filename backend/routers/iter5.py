"""Iteration 5 features: cert preview, file uploads, slide comments,
multi-tenant academy management (SUPER_ADMIN), public academy portals."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, HTTPException, Request, Response, UploadFile,
)
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.config import settings
from core.database import get_db
from core.role_registry import normalize_role_name
from core.security import get_password_hash
from models import (
    Course, CourseSlide, LifecycleStage, Organization, Person, SlideComment, User, UserRole,
)
from services.invitation_service import InvitationService
from services.storage_service import StorageError, get_storage

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml"}


# ── Cert preview (renders sample PDF without persisting) ──────────────
preview_router = APIRouter(prefix="/api/admin/cert-preview", tags=["Cert preview"])


class CertPreviewBody(BaseModel):
    organisation_name: Optional[str] = "Sample Academy"
    organisation_logo_url: Optional[str] = None
    accent_color: Optional[str] = "#6366f1"
    signature_text: Optional[str] = None
    signature_image_url: Optional[str] = None
    footer_text: Optional[str] = None


@preview_router.post("")
def preview_cert(
    body: CertPreviewBody,
    request: Request,
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Render a SAMPLE certificate PDF using the supplied branding — no DB writes.
    Used by the Settings page Live Preview."""
    from services.pdf_certificate_service import render_certificate
    base = settings.public_base_url or str(request.base_url).rstrip("/")
    pdf = render_certificate(
        recipient_name="Jane Sample",
        course_title="Sample Course Title",
        certificate_code="PREVIEW-XXXXX",
        issued_at=datetime.now(timezone.utc),
        verify_url=f"{base}/verify/PREVIEW-XXXXX",
        organisation_name=body.organisation_name or "Sample Academy",
        organisation_logo_url=body.organisation_logo_url,
        accent_color=body.accent_color or "#6366f1",
        signature_text=body.signature_text,
        signature_image_url=body.signature_image_url,
        footer_text=body.footer_text,
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Cache-Control": "no-store"},
    )


# ── File upload (multipart) ──────────────────────────────────────────
uploads_router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

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
            ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif",
            ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
            ".m4v": "video/x-m4v", ".ogg": "video/ogg",
            ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
            ".pdf": "application/pdf"}.get(suffix, "application/octet-stream")
    return Response(
        content=content, media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── Slide comments ────────────────────────────────────────────────────
comments_router = APIRouter(prefix="/api", tags=["Comments"])


class CommentIn(BaseModel):
    body: str
    parent_id: Optional[int] = None


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slide_id: int
    user_id: int
    user_name: Optional[str]
    body: str
    parent_id: Optional[int]
    created_at: datetime


@comments_router.get("/slides/{slide_id}/comments", response_model=List[CommentOut])
def list_comments(slide_id: int, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(get_current_user)):
    rows = db.query(SlideComment).filter(
        SlideComment.slide_id == slide_id, SlideComment.is_deleted.is_(False),
    ).order_by(SlideComment.created_at.asc()).limit(200).all()
    return [CommentOut(
        id=c.id, slide_id=c.slide_id, user_id=c.user_id,
        user_name=db.query(User).filter(User.id == c.user_id).first().name if c.user_id else None,
        body=c.body, parent_id=c.parent_id, created_at=c.created_at,
    ) for c in rows]


@comments_router.post("/slides/{slide_id}/comments", response_model=CommentOut)
def add_comment(slide_id: int, body: CommentIn, db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    slide = db.query(CourseSlide).filter(CourseSlide.id == slide_id).first()
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    if not (body.body or "").strip():
        raise HTTPException(status_code=400, detail="Comment body required")
    c = SlideComment(
        slide_id=slide_id, user_id=current.id, body=body.body.strip()[:5000],
        parent_id=body.parent_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    user = db.query(User).filter(User.id == current.id).first()
    return CommentOut(
        id=c.id, slide_id=c.slide_id, user_id=c.user_id,
        user_name=user.name, body=c.body, parent_id=c.parent_id, created_at=c.created_at,
    )


@comments_router.delete("/slides/{slide_id}/comments/{comment_id}")
def delete_comment(slide_id: int, comment_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)):
    c = db.query(SlideComment).filter(
        SlideComment.id == comment_id, SlideComment.slide_id == slide_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found")
    is_admin = current.has_any_role({"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"})
    if c.user_id != current.id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    c.is_deleted = True
    c.body = "[deleted]"
    db.commit()
    return {"ok": True}


# ── Multi-tenant: SUPER_ADMIN creates academies + invites first admin ─
academies_router = APIRouter(prefix="/api/academies", tags=["Academies"])


class AcademyCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    admin_email: EmailStr
    admin_name: Optional[str] = None


@academies_router.get("")
def list_academies(
    q: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("SUPER_ADMIN")),
):
    """List all academies with optional search (name/slug), status filter, and sort.
    sort: newest | oldest | name | users | courses."""
    from models import OrganizationStatus
    query = db.query(Organization)
    if q:
        like = f"%{q}%"
        query = query.filter((Organization.name.ilike(like)) | (Organization.slug.ilike(like)))
    if status_filter:
        try:
            query = query.filter(Organization.status == OrganizationStatus(status_filter.upper()))
        except ValueError:
            pass
    if sort == "oldest":
        query = query.order_by(Organization.created_at.asc())
    elif sort == "name":
        query = query.order_by(Organization.name.asc())
    else:  # newest (default) — re-sorted below for users/courses
        query = query.order_by(Organization.created_at.desc())
    rows = query.all()
    enriched = [{
        "id": o.id, "name": o.name, "slug": o.slug, "status": o.status.value,
        "theme_preset": o.theme_preset, "primary_color": o.primary_color,
        "user_count": db.query(User).filter(User.organization_id == o.id).count(),
        "course_count": db.query(Course).filter(Course.organization_id == o.id).count(),
        "created_at": o.created_at,
    } for o in rows]
    if sort == "users":
        enriched.sort(key=lambda x: x["user_count"], reverse=True)
    elif sort == "courses":
        enriched.sort(key=lambda x: x["course_count"], reverse=True)
    return enriched


@academies_router.post("")
def create_academy(body: AcademyCreate, request: Request, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("SUPER_ADMIN"))):
    slug = re.sub(r"[^a-z0-9-]", "-", (body.slug or "").lower()).strip("-")
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid slug")
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail="Slug already in use")
    org = Organization(name=body.name, slug=slug, description=body.description)
    db.add(org)
    db.flush()
    # Seed default badge tiers for the new academy
    from models import BadgeTier
    _DEFAULTS = [
        ("FIRST_ENROLLMENT", "First Step",    "🎯", "Enrolled in your first course",  10),
        ("FIRST_COURSE",     "Graduate",      "🎓", "Completed your first course",    50),
        ("EXAM_PASSER",      "Scholar",       "📚", "Passed your first exam",        100),
        ("PERFECT_SCORE",    "Perfectionist", "💯", "Scored 100% on an exam",        200),
        ("COURSE_MASTER",    "Course Master", "🏆", "Completed 5 courses",           500),
    ]
    for idx, (slug_, label, emoji, desc, xp) in enumerate(_DEFAULTS):
        db.add(BadgeTier(
            organization_id=org.id, slug=slug_, label=label, emoji=emoji,
            description=desc, threshold_xp=xp, order_index=idx, is_active=True,
        ))
    # Issue an admin invitation tied to this new academy
    base_url = str(request.base_url).rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    InvitationService(db).create(
        organization_id=org.id, invited_by_id=current.id,
        email=body.admin_email, name=body.admin_name, role="ADMIN",
        app_base_url=base_url,
    )
    from services import audit_service
    audit_service.record(db, current, "ACADEMY_CREATED",
        target_type="organization", target_id=str(org.id),
        metadata={"name": org.name, "slug": org.slug, "admin_email": body.admin_email})
    db.commit()
    return {"ok": True, "academy_id": org.id, "slug": org.slug,
            "admin_invited": body.admin_email}


# ── Public academy portal (one per Organization) ─────────────────────
portal_router = APIRouter(prefix="/api/portal", tags=["Public portal"])


@portal_router.get("/{slug}")
def get_portal(slug: str, db: Session = Depends(get_db)):
    """Public landing data for an academy. Powers /a/<slug> on the frontend."""
    from models import CourseStatus
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if not org:
        raise HTTPException(status_code=404, detail="Academy not found")
    courses = db.query(Course).filter(
        Course.organization_id == org.id,
        Course.status == CourseStatus.PUBLISHED,
    ).order_by(Course.display_order.asc(), Course.created_at.desc()).limit(60).all()
    learner_count = db.query(User).filter(User.organization_id == org.id).count()
    return {
        "organization": {
            "id": org.id, "name": org.name, "slug": org.slug,
            "description": org.description, "logo_url": org.logo_url,
            "primary_color": org.primary_color or "#6366f1",
            "cert_accent_color": org.cert_accent_color,
        },
        "stats": {"learners": learner_count, "courses": len(courses)},
        "courses": [{
            "id": c.id, "title": c.title, "description": c.description,
            "category": c.category, "cover_color": c.cover_color,
            "duration_minutes": c.duration_minutes, "price_cents": c.price_cents,
            "currency": c.currency,
        } for c in courses],
    }


# ── Helper: HMAC-signed outgoing webhook payload (for future use) ────
def sign_outgoing_payload(body: bytes) -> dict:
    """Returns headers to attach to outgoing ERP360 calls.
    `X-Signature` is HMAC-SHA256 of the raw body using the shared secret.
    Receiver (ERP360) verifies the same way it verifies our inbound calls."""
    secret = settings.erp360_sso_shared_secret
    if not secret:
        return {}
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = hmac.new(secret.encode(), body + ts.encode(), hashlib.sha256).hexdigest()
    return {"X-Signature": sig, "X-Timestamp": ts, "X-Service-Token": secret}
