"""Public read-only catalog + certificate verification (Iter P3).

Two flavours of access:

  1. **Anonymous** — `/api/public/certificates/verify/{code}` is fully open
     so a third party (recruiter, university) can verify a certificate
     code without any auth.

  2. **API token with `read:catalog` scope** — `/api/public/catalog` lists
     the org's PUBLISHED courses. Because our API-token auth maps `scopes`
     into `CurrentUser.roles`, we implement a small dedicated dependency
     that specifically requires the `read:catalog` scope. Regular login
     users can also hit this endpoint (any auth'd role sees their own
     org's public catalog).

Anti-abuse notes: the anonymous endpoint returns minimal data (name +
issued date + course title) — no user email / no learner PII. Rate
limiting lives in the ingress / CDN layer.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import Certificate, Course, CourseStatus, Organization, User
from services import rate_limit_service
from services.cache import cached_view, degrade_on_db_error


router = APIRouter(prefix="/api/public", tags=["Public catalog"])


def _catalog_cache_key(
    response: Response = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = None,
    current: CurrentUser = None,
    **_: object,
) -> str:
    """Key: caller's org + normalized query params. TTL-scoped, no PII."""
    org_id = getattr(current, "organization_id", "anon")
    q_norm = (q or "").strip().lower()
    cat_norm = (category or "").strip().lower()
    return f"public_catalog:{org_id}:{q_norm}:{cat_norm}:{limit}"

# Anonymous /verify — 30 hits per IP per minute (shared across replicas
# via Redis when available; per-process fallback otherwise).
_VERIFY_MAX_REQUESTS = 30
_VERIFY_WINDOW_SECS = 60.0


def _client_ip(request: Request) -> str:
    """Real client IP behind an ingress. Trusts the FIRST X-Forwarded-For
    entry (the actual client); the rest are ingress hops that could be
    spoofed. Falls back to request.client.host.

    Iter 26 — When `ALLOW_TEST_TOKEN_HEADER=true` (dev/test only, never
    production), an explicit `X-Test-Client-Ip` header overrides the
    resolved IP so parallel CI workers can pin their own rate-limit
    buckets and stop sharing the K8s ingress's single upstream IP."""
    import os as _os
    if _os.environ.get("ALLOW_TEST_TOKEN_HEADER") == "true":
        test_ip = request.headers.get("x-test-client-ip") or ""
        if test_ip.strip():
            return test_ip.strip()
    fwd = request.headers.get("x-forwarded-for") or ""
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip")
    if real:
        return real
    return getattr(request.client, "host", "0.0.0.0") or "0.0.0.0"


def _ratelimit(ip: str) -> None:
    """Raise 429 if `ip` has exceeded the anonymous verify budget."""
    rate_limit_service.check(
        f"verify:{ip}",
        max_requests=_VERIFY_MAX_REQUESTS,
        window_secs=_VERIFY_WINDOW_SECS,
    )


# ─── Anonymous user-guide PDF downloads ──────────────────────────────
_GUIDES_DIR = "/app/docs/guides"
_GUIDE_FILES = {
    "IFPI_Admin_User_Guide.pdf",
    "IFPI_Student_User_Guide.pdf",
}


@router.get("/guides/{filename}")
def download_user_guide(filename: str, request: Request):
    """Anonymous download of the platform user-guide PDFs.

    Served from the backend (not the SPA dev server) so links stay valid
    regardless of frontend build/restart state. Filenames are whitelisted —
    no path traversal surface.
    """
    _ratelimit(_client_ip(request))
    if filename not in _GUIDE_FILES:
        raise HTTPException(status_code=404, detail="Guide not found")
    path = os.path.join(_GUIDES_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Guide not built yet")
    return FileResponse(path, media_type="application/pdf", filename=filename)


# ─── Anonymous certificate verify ────────────────────────────────────
@router.get("/certificates/verify/{code}")
def verify_certificate(code: str, request: Request, db: Session = Depends(get_db)):
    """Anonymous verification. Rate-limited to 30/min per IP (Redis
    sliding window shared across replicas; degrades to per-process
    memory if Redis is down) so bots can't enumerate. Returns the
    minimum a verifier needs — no PII beyond the holder's display name."""
    _ratelimit(_client_ip(request))
    code = (code or "").strip()
    if not code or len(code) < 4:
        raise HTTPException(status_code=400, detail="Invalid certificate code")

    cert = db.query(Certificate).filter(Certificate.code == code).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    user = db.query(User).filter(User.id == cert.user_id).first()
    course = db.query(Course).filter(Course.id == cert.course_id).first() if cert.course_id else None
    org = db.query(Organization).filter(Organization.id == (user.organization_id if user else 0)).first()

    return {
        "code": cert.code,
        "type": cert.type,
        "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
        "score": cert.score,
        "holder_name": (user.name if user else "Unknown"),
        "course_title": (course.title if course else None),
        "organization_name": (org.name if org else None),
        "verified": True,
    }


# ─── Public catalog (auth'd OR `read:catalog` API token) ────────────
def _require_catalog_access(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """A regular authenticated user always has catalog access to their
    own org. An API-token principal must carry the `read:catalog` scope
    (mapped into `roles`). We detect API tokens by their negative id."""
    is_api_token = current.id < 0
    if is_api_token and "read:catalog" not in current.roles:
        raise HTTPException(
            status_code=403,
            detail="This API token is missing the read:catalog scope",
        )
    return current


@router.get("/catalog")
@cached_view(_catalog_cache_key, ttl_seconds=30.0)
@degrade_on_db_error(_catalog_cache_key)
def public_catalog(
    response: Response,
    q: Optional[str] = Query(default=None, max_length=100),
    category: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(_require_catalog_access),
):
    """List PUBLISHED courses in the caller's org. Read-only, no PII."""
    qry = db.query(Course).filter(
        Course.organization_id == current.organization_id,
        Course.status == CourseStatus.PUBLISHED,
    )
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter((Course.title.ilike(like)) | (Course.description.ilike(like)))
    if category:
        qry = qry.filter(Course.category == category.strip())

    rows = qry.order_by(Course.display_order.asc(), Course.id.asc()).limit(limit).all()
    return {
        "organization_id": current.organization_id,
        "count": len(rows),
        "items": [{
            "id": c.id, "title": c.title, "description": c.description,
            "category": c.category, "duration_minutes": c.duration_minutes,
            "price_cents": c.price_cents, "currency": c.currency,
            "passing_score": c.passing_score,
        } for c in rows],
    }
