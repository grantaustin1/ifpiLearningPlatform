from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from models import Course, Organization, User

from . import portal_router


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
