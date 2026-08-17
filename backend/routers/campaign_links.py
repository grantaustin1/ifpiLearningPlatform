"""Campaign links — multi-use public signup URLs for prospect acquisition."""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth.cookies import (
    set_auth_cookie, set_refresh_cookie, should_include_token_in_body,
)
from auth.dependencies import CurrentUser, requires_roles
from core.config import settings
from core.database import get_db
from models import (
    CampaignLink, Course, CourseStatus, Enrollment, LifecycleStage,
    Organization, Person, User, UserRole,
)
from schemas import LoginResponse, UserOut
from services.auth_service import AuthService

admin_router = APIRouter(prefix="/api/admin/campaign-links",
                         tags=["Campaign Links"])
public_router = APIRouter(prefix="/api/join", tags=["Campaign Links"])


class CampaignCreate(BaseModel):
    name: str
    auto_enroll_course_id: Optional[int] = None


def _out(link: CampaignLink, course_title: Optional[str] = None) -> dict:
    return {
        "id": link.id, "name": link.name, "slug": link.slug,
        "join_path": f"/join/{link.slug}",
        "auto_enroll_course_id": link.auto_enroll_course_id,
        "auto_enroll_course_title": course_title,
        "signup_count": link.signup_count, "is_active": link.is_active,
        "created_at": link.created_at,
    }


@admin_router.post("")
def create_campaign_link(
    body: CampaignCreate, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    course = None
    if body.auto_enroll_course_id:
        course = db.query(Course).filter(
            Course.id == body.auto_enroll_course_id,
            Course.organization_id == current.organization_id,
            Course.status == CourseStatus.PUBLISHED).first()
        if not course:
            raise HTTPException(status_code=404,
                                detail="Course not found or not published")
    link = CampaignLink(
        organization_id=current.organization_id,
        name=body.name.strip()[:120], slug=secrets.token_urlsafe(8),
        auto_enroll_course_id=body.auto_enroll_course_id,
        created_by_id=current.id)
    db.add(link)
    db.commit()
    return _out(link, course.title if course else None)


@admin_router.get("")
def list_campaign_links(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    links = db.query(CampaignLink).filter(
        CampaignLink.organization_id == current.organization_id,
    ).order_by(CampaignLink.created_at.desc()).all()
    cids = [l.auto_enroll_course_id for l in links if l.auto_enroll_course_id]
    titles = ({c.id: c.title for c in db.query(Course).filter(
        Course.id.in_(cids)).all()} if cids else {})
    return [_out(l, titles.get(l.auto_enroll_course_id)) for l in links]


@admin_router.patch("/{link_id}")
def toggle_campaign_link(
    link_id: int, body: dict, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    link = db.query(CampaignLink).filter(
        CampaignLink.id == link_id,
        CampaignLink.organization_id == current.organization_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    if "is_active" in body:
        link.is_active = bool(body["is_active"])
    db.commit()
    return _out(link)


@admin_router.get("/{link_id}/attribution")
def campaign_attribution(
    link_id: int, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    from sqlalchemy import func
    from models import CampaignSignup as Row
    link = db.query(CampaignLink).filter(
        CampaignLink.id == link_id,
        CampaignLink.organization_id == current.organization_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    rows = (db.query(Row.utm_source, Row.utm_medium, func.count(Row.id))
            .filter(Row.campaign_link_id == link_id)
            .group_by(Row.utm_source, Row.utm_medium)
            .order_by(func.count(Row.id).desc()).all())
    # Daily signup trend, last 30 days (gaps zero-filled)
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc).replace(tzinfo=None)
             - timedelta(days=29)).replace(hour=0, minute=0, second=0,
                                           microsecond=0)
    daily = dict(db.query(func.date(Row.created_at), func.count(Row.id))
                 .filter(Row.campaign_link_id == link_id,
                         Row.created_at >= start)
                 .group_by(func.date(Row.created_at)).all())
    trend = []
    for i in range(30):
        d = (start + timedelta(days=i)).date()
        trend.append({"date": d.isoformat(), "signups": int(daily.get(d, 0))})
    return {"link_id": link_id, "total": sum(r[2] for r in rows),
            "trend": trend,
            "breakdown": [{"utm_source": r[0] or "(direct)",
                           "utm_medium": r[1] or "—",
                           "signups": r[2]} for r in rows]}


@admin_router.delete("/{link_id}")
def delete_campaign_link(
    link_id: int, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    link = db.query(CampaignLink).filter(
        CampaignLink.id == link_id,
        CampaignLink.organization_id == current.organization_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()
    return {"ok": True}


# ── Public ────────────────────────────────────────────────────────────

@public_router.get("/{slug}")
def lookup_campaign(slug: str, db: Session = Depends(get_db)):
    link = db.query(CampaignLink).filter(CampaignLink.slug == slug).first()
    if not link or not link.is_active:
        raise HTTPException(status_code=404,
                            detail="This signup link is no longer active")
    org = db.query(Organization).filter(
        Organization.id == link.organization_id).first()
    course = (db.query(Course).filter(Course.id == link.auto_enroll_course_id)
              .first() if link.auto_enroll_course_id else None)
    return {"organization_name": org.name if org else "IFPI Learning",
            "campaign_name": link.name,
            "course_title": course.title if course else None}


class CampaignSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


@public_router.post("/{slug}/signup", response_model=LoginResponse)
def campaign_signup(slug: str, body: CampaignSignup, response: Response,
                    db: Session = Depends(get_db)):
    link = db.query(CampaignLink).filter(CampaignLink.slug == slug).first()
    if not link or not link.is_active:
        raise HTTPException(status_code=404,
                            detail="This signup link is no longer active")
    if len(body.password or "") < 8:
        raise HTTPException(status_code=400,
                            detail="Password must be 8+ characters")
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409,
                            detail="An account with this email already exists — please log in")
    from core.security import get_password_hash
    user = User(email=email, name=body.name.strip()[:120],
                password_hash=get_password_hash(body.password),
                organization_id=link.organization_id, is_active=True)
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role="LEARNER"))
    db.add(Person(user_id=user.id, organization_id=link.organization_id,
                  email=email, name=user.name,
                  lifecycle_stage=LifecycleStage.LEARNER,
                  source=f"campaign:{link.name[:40]}"))
    if link.auto_enroll_course_id:
        course = db.query(Course).filter(
            Course.id == link.auto_enroll_course_id,
            Course.status == CourseStatus.PUBLISHED).first()
        if course and (course.price_cents or 0) == 0:
            db.add(Enrollment(user_id=user.id, course_id=course.id))
    from models import CampaignSignup as CampaignSignupRow
    db.add(CampaignSignupRow(
        campaign_link_id=link.id, user_id=user.id,
        utm_source=(body.utm_source or "").strip()[:120] or None,
        utm_medium=(body.utm_medium or "").strip()[:120] or None,
        utm_campaign=(body.utm_campaign or "").strip()[:120] or None))
    link.signup_count = (link.signup_count or 0) + 1
    db.commit()
    db.refresh(user)

    access, refresh = AuthService(db).issue_tokens(user)
    set_auth_cookie(response, access)
    set_refresh_cookie(response, refresh)
    return LoginResponse(
        access_token=access if should_include_token_in_body() else None,
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserOut(id=user.id, email=user.email, name=user.name,
                     organization_id=user.organization_id,
                     roles=["LEARNER"], points=0),
    )
