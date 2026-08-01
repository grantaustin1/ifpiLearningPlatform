"""Admin entitlement inspection (Iter 39 follow-up).

Support agents get one question all day: **"Why can/can't user X
access course Y?"** — this router surfaces the answer directly from
the §7.1 `EntitlementService` so it can never drift from the
enrollment gate's own logic.

Endpoints:

- `GET /api/admin/entitlements/user/{user_id}` — every published paid
  course in the caller's org + whether this user can access it and
  the source of that access. Free courses omitted (trivially entitled).
- `GET /api/admin/entitlements/user/{user_id}/course/{course_id}` —
  single-course explanation with a support-friendly message.

Admin/Super-admin only. Cross-tenant lookups refused (410 not 404 —
distinguishes "user doesn't exist in your org" from "the endpoint is
gone" for debug clarity).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from models import Course, CourseStatus, User
from services.entitlement_service import EntitlementService


router = APIRouter(prefix="/api/admin/entitlements",
                   tags=["Admin: Entitlements"])


class CourseEntitlement(BaseModel):
    course_id: int
    course_title: str
    price_cents: int
    currency: str
    entitled: bool
    reason: str  # "subscription" | "comp_role" | "none"
    reason_human: str


class UserEntitlementsResponse(BaseModel):
    user_id: int
    email: str
    organization_id: int
    entitlements: List[CourseEntitlement]


_REASON_HUMAN = {
    "comp_role": (
        "User has an admin/instructor role in this course's org — comp "
        "access. If they should NOT have access, revoke their elevated "
        "role first."
    ),
    "subscription": (
        "User has an ACTIVE Subscription for this course (via ERP360 "
        "lite-billing or a manual admin activation)."
    ),
    "none": (
        "No entitlement source matched. The user needs an active "
        "Subscription (via /api/billing/subscribe) or an admin grant."
    ),
}


def _load_target_user(db: Session, current: CurrentUser, user_id: int) -> User:
    u = db.query(User).filter(User.id == user_id).first()
    if not u or u.organization_id != current.organization_id:
        raise HTTPException(
            status_code=410,
            detail=(
                "User not found in your organization. Cross-tenant "
                "entitlement lookups are refused."
            ),
        )
    return u


@router.get("/user/{user_id}", response_model=UserEntitlementsResponse)
def list_user_entitlements(
    user_id: int,
    include_free: bool = False,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_admin()),
<<<<<<< HEAD
):
=======
) -> UserEntitlementsResponse:
>>>>>>> origin/main
    """List every paid course in the caller's org + whether the target
    user can access it and why.

    `include_free=true` returns free courses too (trivially entitled)
    — useful for a full "here's what this user can see" audit view.
    """
    user = _load_target_user(db, current, user_id)
    svc = EntitlementService(db)

    q = db.query(Course).filter(
        Course.organization_id == current.organization_id,
        Course.status == CourseStatus.PUBLISHED,
    )
    if not include_free:
        q = q.filter(Course.price_cents > 0)

    rows: List[CourseEntitlement] = []
    for c in q.order_by(Course.id.asc()).all():
        if c.price_cents <= 0:
            reason = "free"
            entitled = True
            human = "Free course — no entitlement required."
        else:
            entitled = svc.has_course_entitlement(user.id, c.id)
            reason = svc.reason(user.id, c.id) if entitled else "none"
            human = _REASON_HUMAN.get(reason, "")
        rows.append(CourseEntitlement(
            course_id=c.id, course_title=c.title,
            price_cents=c.price_cents, currency=c.currency,
            entitled=entitled, reason=reason, reason_human=human,
        ))
    return UserEntitlementsResponse(
        user_id=user.id, email=user.email,
        organization_id=user.organization_id, entitlements=rows,
    )


class SingleEntitlementResponse(BaseModel):
    user_id: int
    email: str
    course_id: int
    course_title: str
    price_cents: int
    entitled: bool
    reason: str
    reason_human: str
    remediation: Optional[str] = None


@router.get("/user/{user_id}/course/{course_id}",
            response_model=SingleEntitlementResponse)
def get_single_entitlement(
    user_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_admin()),
<<<<<<< HEAD
):
=======
) -> SingleEntitlementResponse:
>>>>>>> origin/main
    """One user, one course — the "why can't they enroll?" answer."""
    user = _load_target_user(db, current, user_id)
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(
            status_code=404,
            detail=f"Course {course_id} not found in your organization.",
        )

    svc = EntitlementService(db)
    if course.price_cents <= 0:
        return SingleEntitlementResponse(
            user_id=user.id, email=user.email,
            course_id=course.id, course_title=course.title,
            price_cents=0, entitled=True, reason="free",
            reason_human="Free course — no entitlement required.",
            remediation=None,
        )

    entitled = svc.has_course_entitlement(user.id, course.id)
    reason = svc.reason(user.id, course.id) if entitled else "none"
    remediation = None if entitled else (
        f"To grant access: (a) create an active Subscription via the "
        f"admin billing UI, or (b) invite the user to complete "
        f"checkout at /api/billing/subscribe with course_id={course.id}."
    )
    return SingleEntitlementResponse(
        user_id=user.id, email=user.email,
        course_id=course.id, course_title=course.title,
        price_cents=course.price_cents,
        entitled=entitled, reason=reason,
        reason_human=_REASON_HUMAN.get(reason, ""),
        remediation=remediation,
    )
