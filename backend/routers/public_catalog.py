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

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import Certificate, Course, CourseStatus, Organization, User


router = APIRouter(prefix="/api/public", tags=["Public catalog"])


# ─── Anonymous certificate verify ────────────────────────────────────
@router.get("/certificates/verify/{code}")
def verify_certificate(code: str, db: Session = Depends(get_db)):
    """Anonymous verification. Returns the minimum a verifier needs:
    holder name, course title, issue date, type. No email. No PII."""
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
def public_catalog(
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
