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

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
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
    base = str(request.base_url).rstrip("/")
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
    """Accepts logo / signature image. Returns a public URL the cert renderer can fetch."""
    if file.content_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {file.content_type}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5MB)")
    suffix = Path(file.filename or "upload").suffix.lower() or ".png"
    safe_name = f"{uuid.uuid4().hex}{_SAFE_NAME.sub('_', suffix)}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(data)
    base = str(request.base_url).rstrip("/") if request else ""
    url = f"{base}/api/uploads/files/{safe_name}"
    return {"url": url, "filename": safe_name, "size": len(data)}


@uploads_router.get("/files/{name}")
def serve_upload(name: str):
    safe_name = _SAFE_NAME.sub("_", name)
    target = UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Best-effort MIME sniffing
    suffix = target.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".svg": "image/svg+xml"}.get(suffix, "application/octet-stream")
    return Response(
        content=target.read_bytes(), media_type=mime,
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
def list_academies(db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("SUPER_ADMIN"))):
    rows = db.query(Organization).order_by(Organization.created_at.desc()).all()
    return [{
        "id": o.id, "name": o.name, "slug": o.slug, "status": o.status.value,
        "user_count": db.query(User).filter(User.organization_id == o.id).count(),
        "course_count": db.query(Course).filter(Course.organization_id == o.id).count(),
        "created_at": o.created_at,
    } for o in rows]


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
    # Issue an admin invitation tied to this new academy
    base_url = str(request.base_url).rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    InvitationService(db).create(
        organization_id=org.id, invited_by_id=current.id,
        email=body.admin_email, name=body.admin_name, role="ADMIN",
        app_base_url=base_url,
    )
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
    ).order_by(Course.created_at.desc()).limit(60).all()
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
