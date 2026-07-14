"""§7.1 follow-up — admin entitlement inspection endpoints.

Locks in:

- Admin CAN list a target user's paid-course entitlements.
- Learner CANNOT hit the endpoint (403).
- Cross-tenant lookup returns 410 (not 404) with a specific message.
- `include_free=true` widens the list to include free courses.
- Single-course endpoint returns `remediation` text when entitled=False.
- Response reason values are drawn from the same set as
  `EntitlementService.reason()`.
- Endpoints work identically under `/api/v1/*` (versioning invariant).
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _learner_id() -> int:
    from core.database import SessionLocal
    from models import User
    db = SessionLocal()
    try:
        return db.query(User).filter_by(email="learner@ifpi.org").first().id
    finally:
        db.close()


def _seed_paid_course(price_cents: int = 4900) -> int:
    from core.database import SessionLocal
    from models import Course, CourseStatus, Organization, User
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="ifpi-main").first()
        admin = db.query(User).filter_by(email="admin@ifpi.org").first()
        c = Course(
            organization_id=org.id,
            title=f"Ent Inspect {uuid.uuid4().hex[:6]}",
            description="",
            price_cents=price_cents, currency="ZAR",
            status=CourseStatus.PUBLISHED,
            created_by_id=admin.id,
        )
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


class TestAdminEntitlementListing:
    def test_admin_can_list_target_user_entitlements(self):
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        uid = _learner_id()
        _seed_paid_course()  # ensure at least one paid course exists

        r = s.get(f"{BASE_URL}/api/admin/entitlements/user/{uid}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user_id"] == uid
        assert body["email"] == "learner@ifpi.org"
        # Every returned row must be a PAID course (default filter).
        assert all(row["price_cents"] > 0 for row in body["entitlements"])
        # Every row has a `reason` in the expected vocabulary.
        for row in body["entitlements"]:
            assert row["reason"] in ("subscription", "comp_role", "none")

    def test_learner_forbidden(self):
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.get(f"{BASE_URL}/api/admin/entitlements/user/{_learner_id()}",
                  timeout=10)
        assert r.status_code == 403

    def test_cross_tenant_user_returns_410(self):
        """Admin in org A must not be able to look up a user in org B."""
        from core.database import SessionLocal
        from datetime import datetime, timezone
        from models import Organization, User

        db = SessionLocal()
        try:
            other = Organization(
                name="Other-Ent-Inspect",
                slug=f"ent-other-{uuid.uuid4().hex[:8]}",
                created_at=datetime.now(timezone.utc),
            )
            db.add(other)
            db.flush()
            foreign = User(
                email=f"foreigner-{uuid.uuid4().hex[:6]}@ifpi.test",
                organization_id=other.id, is_active=True,
                email_verified_at=datetime.now(timezone.utc),
            )
            db.add(foreign)
            db.commit()
            foreign_id = foreign.id
        finally:
            db.close()

        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        r = s.get(f"{BASE_URL}/api/admin/entitlements/user/{foreign_id}",
                  timeout=10)
        assert r.status_code == 410, r.text

    def test_include_free_widens_the_list(self):
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        uid = _learner_id()

        paid_only = s.get(
            f"{BASE_URL}/api/admin/entitlements/user/{uid}", timeout=10,
        ).json()
        with_free = s.get(
            f"{BASE_URL}/api/admin/entitlements/user/{uid}?include_free=true",
            timeout=10,
        ).json()
        assert len(with_free["entitlements"]) >= len(paid_only["entitlements"])
        # Free courses must show reason="free" and entitled=True
        free_rows = [r for r in with_free["entitlements"] if r["price_cents"] == 0]
        for r in free_rows:
            assert r["entitled"] is True
            assert r["reason"] == "free"


class TestAdminEntitlementSingle:
    def test_single_course_denied_returns_remediation(self):
        course_id = _seed_paid_course()
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        r = s.get(
            f"{BASE_URL}/api/admin/entitlements/user/{_learner_id()}/course/{course_id}",
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["entitled"] is False
        assert body["reason"] == "none"
        assert body["remediation"] is not None
        assert "subscri" in body["remediation"].lower()

    def test_single_course_missing_returns_404(self):
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        r = s.get(
            f"{BASE_URL}/api/admin/entitlements/user/{_learner_id()}/course/99999999",
            timeout=10,
        )
        assert r.status_code == 404


class TestVersionedAliasWorks:
    def test_v1_alias_returns_same_shape(self):
        s = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        uid = _learner_id()
        unv = s.get(f"{BASE_URL}/api/admin/entitlements/user/{uid}", timeout=10)
        v1 = s.get(f"{BASE_URL}/api/v1/admin/entitlements/user/{uid}", timeout=10)
        assert unv.status_code == 200 and v1.status_code == 200
        assert unv.json()["user_id"] == v1.json()["user_id"]
        assert v1.headers.get("X-API-Version") == "v1"
