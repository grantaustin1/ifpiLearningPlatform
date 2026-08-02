"""Entitlement abstraction layer (§7.1 IFPI ↔ ERP360 handoff).

Enrollment / access-gate code MUST NOT branch on `billing_mode`. It
asks this service one question:

    Does user X hold a paid entitlement for course Y?

The service knows about every source that can grant an entitlement:

- **`native_stripe` mode** (P1 future): rows written by our Stripe
  checkout webhook handler.
- **`erp360` mode** (current): rows in the `subscriptions` table with
  `status=ACTIVE` — written by the ERP360 lite-billing webhook.
- **Comp / staff grants**: any user with ADMIN, SUPER_ADMIN, or
  INSTRUCTOR roles in the course's org gets implicit access (they
  need to author + preview paid content).

By funneling all these through one method we:
1. Keep enrollment code entirely payment-provider-agnostic
   (`native_stripe` → `erp360` cutover is a webhook-writer swap;
   enrollment code doesn't change).
2. Have a single seam for adding new sources (e.g. voucher redemption
   in Iter 40).
3. Have a single place to audit "who is entitled to this course".

Free courses (`Course.price_cents == 0`) are trivially entitled and
this service is not consulted for them.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import Course, Subscription, SubscriptionStatus, User, UserRole

logger = logging.getLogger(__name__)


# Roles that always have implicit read-access to their org's paid
# content. Instructors need to review + author their own material,
# admins need to preview what learners see.
_COMP_ROLES = {"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"}


class EntitlementService:
    """Single question: does user X hold access to course Y?

    Callers pass ids (not ORM objects) so the service is safe to invoke
    from background workers / webhooks / API-token principals that may
    not have full ORM instances loaded.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def has_course_entitlement(self, user_id: int, course_id: int) -> bool:
        """True if the user can enroll in / access this course based
        on ENTITLEMENTS (paid access). Free courses are handled by
        the caller — this method is only meaningful for paid courses.

        Sources considered (any one grants entitlement):
        - Active `Subscription` for the course.
        - Complimentary role (admin / instructor in the course's org).

        Future sources (Iter 40+):
        - Native Stripe `Payment` row.
        - Voucher redemption.
        - Bundle purchase covering this course.
        """
        # Cheap short-circuit path: comp role.
        if self._has_comp_role(user_id, course_id):
            return True

        # Subscription-backed entitlement (current path).
        sub = (
            self.db.query(Subscription.id)
            .filter(
                Subscription.user_id == user_id,
                Subscription.course_id == course_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .first()
        )
        return sub is not None

    def reason(self, user_id: int, course_id: int) -> str:
        """Human-readable diagnostic for admin dashboards / support
        tickets. Never called from the hot path — safe to run extra
        queries. Returns a short kind: `comp_role`, `subscription`,
        `none`.
        """
        if self._has_comp_role(user_id, course_id):
            return "comp_role"
        if self.has_course_entitlement(user_id, course_id):
            return "subscription"
        return "none"

    # ── Internals ────────────────────────────────────────────────────
    def _has_comp_role(self, user_id: int, course_id: int) -> bool:
        """User is admin/instructor in the course's org."""
        # One tiny join instead of two queries.
        row = (
            self.db.query(UserRole.role)
            .join(Course, Course.id == course_id)
            .join(User, User.id == user_id)
            .filter(
                UserRole.user_id == user_id,
                UserRole.role.in_(_COMP_ROLES),
                # user must be in the course's org
                User.organization_id == Course.organization_id,
            )
            .first()
        )
        return row is not None


def require_course_entitlement(db: Session, user_id: int,
                               course: Course) -> None:
    """Raise 402 if the caller lacks entitlement for a paid course.
    No-op for free courses. Sugar for the enrollment endpoint.
    """
    from fastapi import HTTPException

    if course.price_cents <= 0:
        return
    if EntitlementService(db).has_course_entitlement(user_id, course.id):
        return
    raise HTTPException(
        status_code=402,
        detail=(
            "Paid course — an active entitlement is required. Purchase "
            "via `POST /api/billing/subscribe` or contact your admin "
            "for a grant."
        ),
    )
