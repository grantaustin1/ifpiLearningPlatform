from __future__ import annotations

import re
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import Course, Organization, User
from services.invitation_service import InvitationService

from . import academies_router
from ._schemas import AcademyCreate


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
