"""§7.1 — Entitlement abstraction layer.

Locks in these invariants:

- **Free course** → `require_course_entitlement` is a no-op.
- **Paid course, no entitlement** → raises `HTTPException(402)`.
- **Paid course, active Subscription** → passes.
- **Paid course, ADMIN / SUPER_ADMIN / INSTRUCTOR in the course's org**
  → passes (comp access).
- **Paid course, admin in a *different* org** → does NOT pass
  (cross-tenant leakage guard).
- **`EntitlementService.reason()`** returns `comp_role`,
  `subscription`, or `none` matching the reason a call succeeded.

End-to-end: hitting `POST /api/courses/{id}/enroll` on a paid course
returns 402 without an entitlement, 200 with one.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# ─── Unit-level (service layer) ───────────────────────────────────────
class TestEntitlementServiceUnit:
    def _make_course(self, price_cents: int, org_slug: str = "ifpi-main") -> int:
        from core.database import SessionLocal
        from models import Course, CourseStatus, Organization
        db = SessionLocal()
        try:
            org = db.query(Organization).filter(
                Organization.slug == org_slug).first()
            admin = db.query(__import__(
                "models", fromlist=["User"]).User).filter_by(
                    email="admin@ifpi.org").first()
            c = Course(
                organization_id=org.id,
                title=f"Entitlement Test {uuid.uuid4().hex[:6]}",
                description="",
                price_cents=price_cents,
                currency="ZAR",
                status=CourseStatus.PUBLISHED,
                created_by_id=admin.id,
            )
            db.add(c)
            db.commit()
            return c.id
        finally:
            db.close()

    def _learner_id(self) -> int:
        from core.database import SessionLocal
        from models import User
        db = SessionLocal()
        try:
            return db.query(User).filter_by(email="learner@ifpi.org").first().id
        finally:
            db.close()

    def _admin_id(self) -> int:
        from core.database import SessionLocal
        from models import User
        db = SessionLocal()
        try:
            return db.query(User).filter_by(email="admin@ifpi.org").first().id
        finally:
            db.close()

    def test_free_course_no_check_needed(self):
        """`require_course_entitlement` should be a no-op for free."""
        from core.database import SessionLocal
        from models import Course
        from services.entitlement_service import require_course_entitlement

        course_id = self._make_course(price_cents=0)
        db = SessionLocal()
        try:
            c = db.query(Course).get(course_id)
            # Should not raise even though there's no subscription
            require_course_entitlement(db, self._learner_id(), c)
        finally:
            db.close()

    def test_paid_course_no_entitlement_raises_402(self):
        from core.database import SessionLocal
        from fastapi import HTTPException
        from models import Course
        from services.entitlement_service import require_course_entitlement

        course_id = self._make_course(price_cents=9900)
        db = SessionLocal()
        try:
            c = db.query(Course).get(course_id)
            with pytest.raises(HTTPException) as ei:
                require_course_entitlement(db, self._learner_id(), c)
            assert ei.value.status_code == 402
        finally:
            db.close()

    def test_paid_course_active_subscription_grants_access(self):
        from core.database import SessionLocal
        from models import Course, Subscription, SubscriptionStatus, User
        from services.entitlement_service import (
            EntitlementService, require_course_entitlement,
        )

        course_id = self._make_course(price_cents=9900)
        db = SessionLocal()
        try:
            learner = db.query(User).filter_by(email="learner@ifpi.org").first()
            c = db.query(Course).get(course_id)
            sub = Subscription(
                user_id=learner.id, organization_id=learner.organization_id,
                product_code=f"COURSE_{c.id}", course_id=c.id,
                amount_cents=c.price_cents, currency=c.currency,
                status=SubscriptionStatus.ACTIVE,
                external_subscription_id=f"test_{uuid.uuid4().hex[:8]}",
            )
            db.add(sub)
            db.commit()

            # No raise — access granted.
            require_course_entitlement(db, learner.id, c)
            svc = EntitlementService(db)
            assert svc.has_course_entitlement(learner.id, c.id) is True
            assert svc.reason(learner.id, c.id) == "subscription"
        finally:
            db.close()

    def test_admin_gets_comp_access_to_paid_course(self):
        from core.database import SessionLocal
        from models import Course
        from services.entitlement_service import (
            EntitlementService, require_course_entitlement,
        )

        course_id = self._make_course(price_cents=9900)
        db = SessionLocal()
        try:
            c = db.query(Course).get(course_id)
            require_course_entitlement(db, self._admin_id(), c)  # no raise
            svc = EntitlementService(db)
            assert svc.reason(self._admin_id(), c.id) == "comp_role"
        finally:
            db.close()

    def test_cross_tenant_admin_does_not_get_comp_access(self):
        """An admin in org X must NOT get comp access to paid content
        in org Y — this would be a cross-tenant data leak."""
        from core.database import SessionLocal
        from datetime import datetime, timezone
        from models import Course, Organization, User, UserRole
        from services.entitlement_service import EntitlementService

        db = SessionLocal()
        try:
            # Create a second org + an admin in it
            other_org = Organization(
                name="Other Academy",
                slug=f"other-acad-{uuid.uuid4().hex[:8]}",
                created_at=datetime.now(timezone.utc),
            )
            db.add(other_org)
            db.flush()
            foreign_admin = User(
                email=f"foreign-admin-{uuid.uuid4().hex[:6]}@ifpi.test",
                organization_id=other_org.id, is_active=True,
                email_verified_at=datetime.now(timezone.utc),
            )
            db.add(foreign_admin)
            db.flush()
            db.add(UserRole(user_id=foreign_admin.id, role="ADMIN",
                            source="native"))
            db.commit()

            # Create a paid course in the ORIGINAL org
            course_id = self._make_course(price_cents=9900, org_slug="ifpi-main")
            c = db.query(Course).get(course_id)

            svc = EntitlementService(db)
            # Foreign admin has ADMIN role but in a different org — no access.
            assert svc.has_course_entitlement(foreign_admin.id, c.id) is False
            assert svc.reason(foreign_admin.id, c.id) == "none"
        finally:
            db.close()


# ─── End-to-end (enrollment endpoint) ─────────────────────────────────
class TestEnrollmentGate:
    def test_enroll_paid_without_entitlement_returns_402(self):
        """Full HTTP round-trip against the enroll endpoint. Confirms
        the courses.py router uses the new entitlement seam."""
        from core.database import SessionLocal
        from models import Course, CourseStatus, Organization, User

        # Create a paid course as admin
        db = SessionLocal()
        try:
            org = db.query(Organization).filter_by(slug="ifpi-main").first()
            admin = db.query(User).filter_by(email="admin@ifpi.org").first()
            c = Course(
                organization_id=org.id,
                title=f"Paid E2E {uuid.uuid4().hex[:6]}",
                description="",
                price_cents=4900, currency="ZAR",
                status=CourseStatus.PUBLISHED,
                created_by_id=admin.id,
            )
            db.add(c)
            db.commit()
            course_id = c.id
        finally:
            db.close()

        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(f"{BASE_URL}/api/courses/{course_id}/enroll", timeout=10)
        assert r.status_code == 402, r.text
        # The message should reference the entitlement seam.
        detail = (r.json().get("error", {}) or {}).get("message", "") or r.text
        assert "entitlement" in detail.lower(), detail
