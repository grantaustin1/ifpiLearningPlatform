from __future__ import annotations

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from core.database import get_db
from models import Course, CourseStatus, Enrollment, Organization

from . import catalog_router


@catalog_router.get("/organizations")
def catalog_organizations(db: Session = Depends(get_db)):
    """Iter 27 — Cross-tenant marketplace search: list opted-in
    organizations with a public course. Powers the org-filter dropdown
    on the marketplace catalog page."""
    rows = (
        db.query(
            Organization.id, Organization.name, Organization.logo_url,
            func.count(Course.id).label("course_count"),
        )
        .join(Course, Course.organization_id == Organization.id)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .filter(Course.status == CourseStatus.PUBLISHED)
        .group_by(Organization.id, Organization.name, Organization.logo_url)
        .order_by(func.count(Course.id).desc(), Organization.name.asc())
        .all()
    )
    return [
        {"id": r.id, "name": r.name, "logo_url": r.logo_url,
         "course_count": r.course_count}
        for r in rows
    ]


@catalog_router.get("")
def catalog(q: str | None = Query(None),
            category: str | None = Query(None),
            org: int | None = Query(None, description="Filter by organization id (Iter 27)"),
            featured: bool = Query(False),
            sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|most_enrolled)$"),
            page: int = Query(1, ge=1),
            page_size: int = Query(24, ge=1, le=100),
            db: Session = Depends(get_db)):
    query = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
    )
    if q:
        # Iter 27 — Cross-tenant search: match on course title
        # OR organization name so a search for "IFPI" surfaces
        # courses published by "IFPI Academy" etc.
        like = f"%{q}%"
        query = query.filter(or_(
            Course.title.ilike(like),
            Organization.name.ilike(like),
        ))
    if category:
        query = query.filter(Course.category == category)
    if org is not None:
        query = query.filter(Course.organization_id == org)
    total = query.count()
    if featured:
        # Featured = top 6 by enrollment count (SQL-side)
        enroll_sq = (
            db.query(Enrollment.course_id, func.count(Enrollment.id).label("n"))
            .group_by(Enrollment.course_id).subquery()
        )
        courses = (
            query.outerjoin(enroll_sq, enroll_sq.c.course_id == Course.id)
                 .order_by(func.coalesce(enroll_sq.c.n, 0).desc(), Course.created_at.desc())
                 .options(selectinload(Course.slides), selectinload(Course.enrollments))
                 .limit(6).all()
        )
    else:
        # Apply sort
        if sort == "price_asc":
            query = query.order_by(Course.price_cents.asc(), Course.created_at.desc())
        elif sort == "price_desc":
            query = query.order_by(Course.price_cents.desc(), Course.created_at.desc())
        elif sort == "most_enrolled":
            enroll_sq = (
                db.query(Enrollment.course_id, func.count(Enrollment.id).label("n"))
                .group_by(Enrollment.course_id).subquery()
            )
            query = (query.outerjoin(enroll_sq, enroll_sq.c.course_id == Course.id)
                          .order_by(func.coalesce(enroll_sq.c.n, 0).desc(),
                                    Course.created_at.desc()))
        else:  # newest
            query = query.order_by(Course.created_at.desc())
        # Iter 38 — was 52 queries (n+1 on `c.slides` and `c.enrollments`
        # per course). `selectinload` collapses to 3 queries: the paged
        # course rows + one for slides + one for enrollments.
        courses = (query
                   .options(selectinload(Course.slides), selectinload(Course.enrollments))
                   .offset((page - 1) * page_size).limit(page_size).all())
    # Bulk-load orgs for the resulting courses
    org_ids = {c.organization_id for c in courses}
    orgs = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}
    cats = [r[0] for r in db.query(Course.category).filter(
        Course.status == CourseStatus.PUBLISHED, Course.category.isnot(None),
    ).distinct().all() if r[0]]
    return {
        "courses": [{
            "id": c.id, "title": c.title, "description": c.description,
            "category": c.category, "cover_color": c.cover_color,
            "duration_minutes": c.duration_minutes, "price_cents": c.price_cents,
            "currency": c.currency, "slide_count": len(c.slides),
            "enrollment_count": len(c.enrollments),
            "organization": ({
                "id": orgs[c.organization_id].id,
                "name": orgs[c.organization_id].name,
                "logo_url": orgs[c.organization_id].logo_url,
            } if c.organization_id in orgs else None),
        } for c in courses],
        "categories": cats,
        "total": total, "page": page, "page_size": page_size,
        "sort": sort,
    }


@catalog_router.get("/{course_id}")
def catalog_detail(course_id: int, db: Session = Depends(get_db)):
    """Public course detail — shown on marketplace product page."""
    course = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.id == course_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or not publicly listed")
    org = db.query(Organization).filter(Organization.id == course.organization_id).first()
    slides = sorted(course.slides, key=lambda s: s.order_index)[:8]
    return {
        "id": course.id, "title": course.title, "description": course.description,
        "category": course.category, "cover_color": course.cover_color,
        "duration_minutes": course.duration_minutes, "price_cents": course.price_cents,
        "currency": course.currency,
        "slide_count": len(course.slides),
        "enrollment_count": len(course.enrollments),
        "syllabus_preview": [{"title": s.title, "order_index": s.order_index} for s in slides],
        "organization": {
            "id": org.id, "name": org.name, "logo_url": org.logo_url,
        } if org else None,
    }
