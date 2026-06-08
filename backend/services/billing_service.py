"""Billing service — STUB mode for v1
webhook-driven via ERP360 once `BILLING_LIVE_MODE=true`.

Public surface is stable so frontend code doesn't change when going live.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from models import (
    BillingEvent, Course, Subscription, SubscriptionStatus, User,
)
from services.gamification_service import GamificationService

logger = logging.getLogger(__name__)


class BillingService:
    def __init__(self, db: Session):
        self.db = db

    # ── Subscribe (caller-facing) ────────────────────────────────────
    def subscribe(self, user: User, course: Course) -> dict:
        if course.price_cents <= 0:
            raise HTTPException(status_code=400, detail="This course is free — just enrol")

        existing = self.db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.course_id == course.id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]),
        ).first()
        if existing:
            return {
                "subscription_id": existing.id, "status": existing.status.value,
                "checkout_url": None, "is_stub": not settings.billing_live_mode,
                "message": "You already have an active subscription for this course.",
            }

        sub = Subscription(
            user_id=user.id, organization_id=user.organization_id,
            product_code=f"COURSE_{course.id}", course_id=course.id,
            amount_cents=course.price_cents, currency=course.currency,
            status=SubscriptionStatus.PENDING,
        )
        self.db.add(sub)
        self.db.flush()

        if settings.billing_live_mode and settings.erp360_base_url:
            url, ext_id = self._create_erp360_profile(sub, user, course)
            sub.external_subscription_id = ext_id
            self.db.commit()
            return {"subscription_id": sub.id, "status": sub.status.value,
                    "checkout_url": url, "is_stub": False,
                    "message": "Redirecting to secure checkout..."}

        # STUB: pretend the subscription went active immediately
        sub.status = SubscriptionStatus.ACTIVE
        sub.external_subscription_id = f"stub_{secrets.token_hex(8)}"
        self.db.add(BillingEvent(
            user_id=user.id, subscription_id=sub.id,
            event_type="subscription.activated.stub",
            external_id=sub.external_subscription_id,
            payload={"reason": "BILLING_LIVE_MODE=false; auto-activated in stub mode"},
        ))
        self.db.commit()
        return {"subscription_id": sub.id, "status": "ACTIVE",
                "checkout_url": None, "is_stub": True,
                "message": "Billing is in stub mode — subscription auto-activated for testing."}

    def _create_erp360_profile(self, sub: Subscription, user: User,
                               course: Course) -> tuple[str, str]:
        """Real path: hands off to ERP360's lite-billing module."""
        payload = {
            "external_id": f"ifpi_sub_{sub.id}",
            "email": user.email, "name": user.name,
            "amount_cents": sub.amount_cents, "currency": sub.currency,
            "frequency": "MONTHLY",
            "product_code": sub.product_code,
            "metadata": {"ifpi_course_id": course.id, "ifpi_user_id": user.id},
            "success_url": f"{settings.allowed_origins.split(',')[0]}/billing/success",
            "webhook_url": f"{settings.erp360_base_url}/webhooks/ifpi-billing",
        }
        try:
            with httpx.Client(timeout=15) as cli:
                r = cli.post(
                    f"{settings.erp360_base_url}/api/lite-billing/profiles",
                    json=payload,
                    headers={"X-Service-Token": settings.erp360_sso_shared_secret},
                )
                r.raise_for_status()
                data = r.json()
                return data["checkout_url"], data["external_id"]
        except Exception as e:
            logger.exception("ERP360 billing handoff failed: %s", e)
            raise HTTPException(status_code=502, detail="Billing service unavailable")

    # ── Webhook handler ──────────────────────────────────────────────
    def verify_webhook_signature(self, body: bytes, signature: Optional[str]) -> bool:
        secret = settings.erp360_billing_webhook_secret
        if not secret:
            # In stub mode we don't reject — log and proceed for dev convenience
            return not settings.billing_live_mode
        if not signature:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def handle_event(self, event_type: str, data: dict) -> dict:
        external_id = data.get("external_id") or data.get("subscription_external_id")
        sub: Optional[Subscription] = None
        if external_id:
            sub = self.db.query(Subscription).filter(
                Subscription.external_subscription_id == external_id,
            ).first()

        # Always audit, even unknown events
        self.db.add(BillingEvent(
            user_id=sub.user_id if sub else None,
            subscription_id=sub.id if sub else None,
            event_type=event_type, external_id=external_id, payload=data,
        ))

        if sub:
            mapping = {
                "subscription.activated": SubscriptionStatus.ACTIVE,
                "payment.succeeded":      SubscriptionStatus.ACTIVE,
                "payment.failed":         SubscriptionStatus.PAST_DUE,
                "subscription.cancelled": SubscriptionStatus.CANCELLED,
            }
            if event_type in mapping:
                sub.status = mapping[event_type]
                sub.updated_at = datetime.now(timezone.utc)
                if event_type == "payment.succeeded":
                    GamificationService(self.db).notify(
                        sub.user_id, "PAYMENT_OK",
                        "Payment received", "Your subscription is up to date.", "/billing",
                    )

        self.db.commit()
        return {"received": True, "matched_subscription": bool(sub)}
