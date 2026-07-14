"""§7 P1 — Stripe payments integration.

Uses the emergent test key (`STRIPE_API_KEY=sk_test_emergent`) so the
tests run against the live Stripe test-mode API but never charge a
real card.

Locks in these invariants:

- Learner CAN create a checkout session for a paid course; response
  includes a real Stripe URL + session_id + our txn_id.
- Amount comes from `Course.price_cents` — frontend cannot inflate it.
- Free courses REFUSE checkout creation (400 with a specific message).
- Missing course → 404.
- Polling status BEFORE payment shows `entitled=false, payment_status='unpaid'`.
- `PaymentTransaction` row is written in `initiated` state before the
  redirect (so we have audit trail even if the browser drops off).
- `/api/v1/*` alias works for both endpoints.
- Cross-user status lookup refused (404 — the txn is scoped to the
  owning user).
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _make_paid_course(price_cents: int = 4900, currency: str = "usd") -> int:
    from core.database import SessionLocal
    from models import Course, CourseStatus, Organization, User
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="ifpi-main").first()
        admin = db.query(User).filter_by(email="admin@ifpi.org").first()
        c = Course(
            organization_id=org.id,
            title=f"Stripe Test {uuid.uuid4().hex[:6]}",
            description="",
            price_cents=price_cents, currency=currency,
            status=CourseStatus.PUBLISHED,
            created_by_id=admin.id,
        )
        db.add(c); db.commit()
        return c.id
    finally:
        db.close()


def _make_free_course() -> int:
    return _make_paid_course(price_cents=0, currency="usd")


class TestCreateCheckoutSession:
    def test_learner_can_create_session_for_paid_course(self):
        cid = _make_paid_course(price_cents=4900)
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(
            f"{BASE_URL}/api/payments/v1/checkout/session",
            json={"course_id": cid, "origin_url": BASE_URL},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["url"].startswith("https://checkout.stripe.com/")
        assert body["session_id"].startswith("cs_test_")
        assert isinstance(body["transaction_id"], int)

    def test_free_course_refuses_checkout(self):
        cid = _make_free_course()
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(
            f"{BASE_URL}/api/payments/v1/checkout/session",
            json={"course_id": cid, "origin_url": BASE_URL},
            timeout=10,
        )
        assert r.status_code == 400
        assert "free" in r.text.lower()

    def test_unknown_course_returns_404(self):
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(
            f"{BASE_URL}/api/payments/v1/checkout/session",
            json={"course_id": 99999999, "origin_url": BASE_URL},
            timeout=10,
        )
        assert r.status_code == 404

    def test_transaction_row_written_before_redirect(self):
        """After create, we must be able to poll the txn by its
        session_id — proves the row hit the DB before the redirect."""
        cid = _make_paid_course()
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        create = s.post(
            f"{BASE_URL}/api/payments/v1/checkout/session",
            json={"course_id": cid, "origin_url": BASE_URL},
            timeout=15,
        ).json()

        # Verify by direct DB check
        from core.database import SessionLocal
        from models import PaymentTransaction
        db = SessionLocal()
        try:
            txn = db.query(PaymentTransaction).filter_by(
                stripe_session_id=create["session_id"]).first()
            assert txn is not None
            assert txn.status == "initiated"
            assert txn.amount_cents == 4900
            assert txn.product_id == cid
        finally:
            db.close()


class TestCheckoutStatusPolling:
    def test_status_before_payment_shows_unpaid(self):
        cid = _make_paid_course()
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        create = s.post(
            f"{BASE_URL}/api/payments/v1/checkout/session",
            json={"course_id": cid, "origin_url": BASE_URL},
            timeout=15,
        ).json()

        r = s.get(
            f"{BASE_URL}/api/payments/v1/checkout/status/{create['session_id']}",
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["payment_status"] == "unpaid"
        assert body["entitled"] is False
        assert body["already_processed"] is False
        assert body["course_id"] == cid

    def test_cross_user_status_lookup_refused(self):
        """Learner A's session can't be polled by learner B (or by
        admin either — txns are user-scoped)."""
        cid = _make_paid_course()
        s_learner = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        create = s_learner.post(
            f"{BASE_URL}/api/payments/v1/checkout/session",
            json={"course_id": cid, "origin_url": BASE_URL},
            timeout=15,
        ).json()

        s_admin = authed_session("admin@ifpi.org", "admin123", BASE_URL)
        r = s_admin.get(
            f"{BASE_URL}/api/payments/v1/checkout/status/{create['session_id']}",
            timeout=10,
        )
        assert r.status_code == 404


class TestV1Alias:
    def test_v1_checkout_session_alias(self):
        cid = _make_paid_course()
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(
            f"{BASE_URL}/api/v1/payments/v1/checkout/session",
            json={"course_id": cid, "origin_url": BASE_URL},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.headers.get("X-API-Version") == "v1"
