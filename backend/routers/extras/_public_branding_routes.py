from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from models import Organization

from . import public_branding_router


@public_branding_router.get("/public")
def public_branding(slug: str | None = None, db: Session = Depends(get_db)):
    """Fetch org branding by slug (query param). If no slug is passed, we
    return the FIRST org in the DB — sensible for single-tenant deployments
    like IFPI's initial rollout. The response is intentionally minimal:
    just brand name, logo URL, primary colour, accent colour."""
    q = db.query(Organization)
    if slug:
        q = q.filter(Organization.slug == slug)
    else:
        q = q.order_by(Organization.id.asc())
    org = q.first()
    if not org:
        return {"name": "Learning Platform", "logo_url": None,
                "primary_color": "#6366f1", "accent_color": "#F5A500",
                "slug": None}
    return {
        "name": org.name,
        "slug": org.slug,
        "logo_url": org.logo_url,
        "primary_color": org.primary_color or "#6366f1",
        "accent_color": org.cert_accent_color or org.primary_color or "#F5A500",
    }
