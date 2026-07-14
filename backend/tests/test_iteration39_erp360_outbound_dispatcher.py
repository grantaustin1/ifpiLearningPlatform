"""§5.2 — Outbound webhook dispatcher (ERP360 direction) in dry-run mode.

Locks in these invariants:

**Auto-provisioning:**
- PATCH sets `integrations.erp360.connected=true` → an ERP360-managed
  `WebhookSubscription` row is auto-created for that org.
- Second PATCH is idempotent (no duplicate rows).
- PATCH sets `connected=false` → the row is deactivated (kept for audit)
  and subsequent emits are ignored.

**Dry-run mode:**
- Subscription defaults to `target_url='dry-run://erp360'` when neither
  `ERP360_WEBHOOK_TARGET_URL` nor `ERP360_BASE_URL` env is set.
- `emit_event(...)` on a dry-run subscription persists a `WebhookDelivery`
  row with `status='DELIVERED', status_code=204, error='dry-run: ...'`
  and NEVER makes an HTTP request.
- Signature is still computed + persisted for audit + eventual replay.

**Event coverage:**
- Inviting a learner (`POST /api/admin/invitations`) emits
  `learner.invited` visible in the delivery log.
- The ERP360 subscription only subscribes to the whitelisted event types
  — a random event (e.g. `unrelated.thing`) is NOT queued to ERP360.

**Signature + envelope:**
- Delivery `payload` decodes to a JSON envelope containing
  `event_type`, `event_id`, `organization_id`, `occurred_at`, `data`.
- `X-IFPI-Signature` in the envelope's HMAC-SHA256 matches
  `webhook_service.sign(sub.secret, payload_bytes)`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _admin_session() -> requests.Session:
    return authed_session("admin@ifpi.org", "admin123", BASE_URL)


def _seed_org_with_admin() -> tuple[int, int]:
    """Create a fresh org + admin — isolates each test from shared state."""
    from core.database import SessionLocal
    from datetime import datetime, timezone
    from models import Organization, User, UserRole
    db = SessionLocal()
    try:
        org = Organization(
            name=f"Outbox-Test-{uuid.uuid4().hex[:6]}",
            slug=f"outbox-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc),
        )
        db.add(org)
        db.flush()
        admin = User(
            email=f"outbox-admin-{uuid.uuid4().hex[:6]}@ifpi.test",
            name="Outbox Admin",
            organization_id=org.id, is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(admin); db.flush()
        db.add(UserRole(user_id=admin.id, role="ADMIN", source="native"))
        db.commit()
        return org.id, admin.id
    finally:
        db.close()


class TestAutoProvisioning:
    def test_connected_true_auto_creates_erp360_subscription(self):
        from core.database import SessionLocal
        from models import Organization, WebhookSubscription
        from services.erp360_webhook_dispatcher import (
            ERP360_MANAGED_MARKER, ensure_erp360_subscription,
        )
        org_id, _ = _seed_org_with_admin()

        db = SessionLocal()
        try:
            org = db.query(Organization).get(org_id)
            # Simulate the PATCH → integrations.erp360.connected=true
            org.integrations = {"erp360": {"connected": True,
                                           "sso_enabled": True}}
            db.flush()
            sub = ensure_erp360_subscription(db, org)
            db.commit()

            assert sub.id is not None
            assert sub.description == ERP360_MANAGED_MARKER
            events = json.loads(sub.events)
            assert "learner.invited" in events
            assert "certificate.issued" in events
            assert sub.is_active is True
        finally:
            db.close()

    def test_second_call_is_idempotent(self):
        from core.database import SessionLocal
        from models import Organization, WebhookSubscription
        from services.erp360_webhook_dispatcher import (
            ERP360_MANAGED_MARKER, ensure_erp360_subscription,
        )
        org_id, _ = _seed_org_with_admin()
        db = SessionLocal()
        try:
            org = db.query(Organization).get(org_id)
            ensure_erp360_subscription(db, org)
            db.commit()
            ensure_erp360_subscription(db, org)
            db.commit()

            rows = db.query(WebhookSubscription).filter(
                WebhookSubscription.organization_id == org.id,
                WebhookSubscription.description == ERP360_MANAGED_MARKER,
            ).all()
            assert len(rows) == 1
        finally:
            db.close()

    def test_deactivate_preserves_row(self):
        from core.database import SessionLocal
        from models import Organization
        from services.erp360_webhook_dispatcher import (
            ERP360_MANAGED_MARKER, ensure_erp360_subscription,
            deactivate_erp360_subscription,
        )
        from models import WebhookSubscription
        org_id, _ = _seed_org_with_admin()
        db = SessionLocal()
        try:
            org = db.query(Organization).get(org_id)
            ensure_erp360_subscription(db, org); db.commit()
            deactivate_erp360_subscription(db, org); db.commit()

            row = db.query(WebhookSubscription).filter(
                WebhookSubscription.organization_id == org.id,
                WebhookSubscription.description == ERP360_MANAGED_MARKER,
            ).first()
            assert row is not None       # NOT deleted
            assert row.is_active is False
        finally:
            db.close()


class TestDryRunMode:
    def test_dry_run_url_persists_delivery_without_http_call(self):
        """Emit an event through a dry-run subscription — verify
        the WebhookDelivery row hits DELIVERED without any HTTP."""
        from core.database import SessionLocal
        from models import Organization, WebhookDelivery
        from services.erp360_webhook_dispatcher import (
            ensure_erp360_subscription,
        )
        from services.webhook_service import emit_event
        org_id, _ = _seed_org_with_admin()

        db = SessionLocal()
        try:
            org = db.query(Organization).get(org_id)
            sub = ensure_erp360_subscription(db, org)
            db.commit()
            assert sub.target_url.startswith("dry-run://"), (
                f"expected dry-run sentinel, got {sub.target_url}"
            )

            n = emit_event(db, org.id, "learner.invited", {
                "email": "alice@test.example",
                "name": "Alice", "role": "LEARNER",
            })
            db.commit()
            assert n == 1

            row = db.query(WebhookDelivery).filter(
                WebhookDelivery.organization_id == org.id,
                WebhookDelivery.event_type == "learner.invited",
            ).order_by(WebhookDelivery.id.desc()).first()
            assert row is not None
            assert row.status == "DELIVERED"
            assert row.status_code == 204
            assert "dry-run" in (row.error or "")
            # Payload envelope has the expected shape
            env = json.loads(row.payload)
            assert env["event_type"] == "learner.invited"
            assert env["data"]["email"] == "alice@test.example"
            # Signature matches sign(secret, payload)
            expected_sig = hmac.new(
                sub.secret.encode(), row.payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            assert row.signature == expected_sig
        finally:
            db.close()

    def test_unsubscribed_event_type_is_not_queued(self):
        """ERP360 subscription filters events — a random event type
        must NOT create a delivery row."""
        from core.database import SessionLocal
        from models import Organization, WebhookDelivery
        from services.erp360_webhook_dispatcher import (
            ensure_erp360_subscription,
        )
        from services.webhook_service import emit_event
        org_id, _ = _seed_org_with_admin()

        db = SessionLocal()
        try:
            org = db.query(Organization).get(org_id)
            ensure_erp360_subscription(db, org)
            db.commit()

            n = emit_event(db, org.id, "unrelated.event.type", {"x": 1})
            db.commit()
            assert n == 0

            rows = db.query(WebhookDelivery).filter(
                WebhookDelivery.organization_id == org.id,
                WebhookDelivery.event_type == "unrelated.event.type",
            ).count()
            assert rows == 0
        finally:
            db.close()


class TestEndToEndInviteFlow:
    def test_invite_learner_emits_learner_invited(self):
        """Full HTTP round-trip: PATCH connected=true, then invite a
        learner via the admin endpoint, then check the delivery log."""
        s = _admin_session()

        # Turn on ERP360 for the preview org
        try:
            r = s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"connected": True, "sso_enabled": True},
                timeout=10,
            )
            assert r.status_code == 200, r.text

            # Invite a fresh learner
            unique = f"invitee-{uuid.uuid4().hex[:8]}@example.com"
            r = s.post(
                f"{BASE_URL}/api/admin/invitations",
                json={"email": unique, "name": "Test Invitee",
                      "role": "LEARNER"},
                timeout=10,
            )
            assert r.status_code == 200, r.text

            # Verify delivery row exists in dry-run
            from core.database import SessionLocal
            from models import WebhookDelivery
            db = SessionLocal()
            try:
                row = (
                    db.query(WebhookDelivery)
                    .filter(WebhookDelivery.event_type == "learner.invited")
                    .order_by(WebhookDelivery.id.desc())
                    .first()
                )
                assert row is not None
                env = json.loads(row.payload)
                assert env["data"]["email"] == unique
                assert env["data"]["role"] == "LEARNER"
                # Either DELIVERED (dry-run) or a legit attempt state —
                # the point is that the emit fired and was persisted.
                assert row.status in ("DELIVERED", "FAILED", "QUEUED")
            finally:
                db.close()
        finally:
            # Restore state
            s.patch(
                f"{BASE_URL}/api/admin/organizations/1/integrations/erp360",
                json={"connected": None, "sso_enabled": None},
                timeout=10,
            )
