"""Stripe payments — course purchase via Stripe Checkout (Iter 39 P1).

Flow (mirrors the emergentintegrations playbook):

1. Learner clicks "Buy course" on the paid course detail page.
2. Frontend calls `POST /api/payments/v1/checkout/session` with
   `{ course_id, origin_url }`. **Frontend never sends the amount** —
   server reads `Course.price_cents`.
3. Backend creates a `PaymentTransaction` row (status=`initiated`),
   creates a Stripe Checkout Session, and returns `{ url, session_id }`.
4. Frontend redirects the browser to `data.url`.
5. On return, frontend polls `GET /api/payments/v1/checkout/status/{sid}`
   which:
   - Fetches the checkout status from Stripe.
   - Updates the `PaymentTransaction` row.
   - On the first `paid` observation, activates a `Subscription` row so
     the existing `EntitlementService` grants access.
6. The `POST /api/webhook/stripe` receiver does the same fulfillment
   server-side. Whichever path (poll or webhook) reaches "paid" first
   activates; the second is a no-op (idempotent).

The `Course.currency` field is honoured. USD-only for crypto payments
(not currently enabled).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import (
    Course, CourseStatus, PaymentTransaction, Subscription,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/v1", tags=["Payments (Stripe)"])
webhook_router = APIRouter(prefix="/api/webhook", tags=["Payments (Stripe)"])


def _get_stripe_key() -> str:
    key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Stripe is not configured. Set STRIPE_API_KEY in the "
                "backend environment."
            ),
        )
    return key


def _stripe_checkout(request: Request):
    """Build a StripeCheckout client. Lazy-imported so the app boots
    even when `emergentintegrations` isn't installed in a lean CI
    image."""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=_get_stripe_key(), webhook_url=webhook_url)


# ─── Schemas ──────────────────────────────────────────────────────────
class CheckoutSessionIn(BaseModel):
    course_id: int
    # Frontend passes its origin so the backend can build a
    # correctly-scoped success/cancel URL. Never trusted for amounts.
    origin_url: str = Field(min_length=1, max_length=500)


class CheckoutSessionOut(BaseModel):
    url: str
    session_id: str
    transaction_id: int


class CheckoutStatusOut(BaseModel):
    session_id: str
    status: str
    payment_status: Optional[str] = None
    amount_cents: int
    currency: str
    course_id: int
    entitled: bool
    already_processed: bool


# ─── Helpers ──────────────────────────────────────────────────────────
def _fulfill_if_paid(
    db: Session, txn: PaymentTransaction, checkout_status: dict,
) -> bool:
    """Idempotent fulfillment. Returns `True` iff THIS call is the one
    that flipped the transaction from unfulfilled → paid.

    `checkout_status` should have at least `status` and `payment_status`
    (from Stripe's session object).
    """
    stripe_payment_status = (checkout_status.get("payment_status") or "").lower()
    stripe_status = (checkout_status.get("status") or "").lower()

    txn.status = stripe_status or txn.status
    txn.payment_status = stripe_payment_status or txn.payment_status

    if stripe_payment_status != "paid":
        return False

    if txn.fulfilled_at is not None:
        return False  # already processed

    # Activate the Subscription so EntitlementService grants access
    existing = db.query(Subscription).filter(
        Subscription.user_id == txn.user_id,
        Subscription.course_id == txn.product_id,
        Subscription.status == SubscriptionStatus.ACTIVE,
    ).first()

    if existing is None:
        db.add(Subscription(
            user_id=txn.user_id,
            organization_id=txn.organization_id,
            product_code=f"COURSE_{txn.product_id}",
            course_id=txn.product_id,
            status=SubscriptionStatus.ACTIVE,
            amount_cents=txn.amount_cents,
            currency=txn.currency,
            external_subscription_id=f"stripe_{txn.stripe_session_id}",
        ))

    txn.status = "paid"
    txn.payment_status = "paid"
    txn.fulfilled_at = datetime.now(timezone.utc)
    db.commit()
    return True


# ─── Endpoints ────────────────────────────────────────────────────────
@router.post("/checkout/session", response_model=CheckoutSessionOut)
async def create_checkout_session(
    body: CheckoutSessionIn,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for the target course.
    Amount is server-authoritative — read from `Course.price_cents`.
    """
    course = db.query(Course).filter(
        Course.id == body.course_id,
        Course.organization_id == current.organization_id,
        Course.status == CourseStatus.PUBLISHED,
    ).first()
    if not course:
        raise HTTPException(status_code=404,
                            detail="Course not found or not published")
    if course.price_cents <= 0:
        raise HTTPException(status_code=400,
                            detail="This course is free — no payment needed")

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/catalog/{course.id}"

    from emergentintegrations.payments.stripe.checkout import (
        CheckoutSessionRequest,
    )
    checkout = _stripe_checkout(request)
    checkout_req = CheckoutSessionRequest(
        # emergentintegrations wants amount as float. Convert cents → major.
        amount=round(course.price_cents / 100.0, 2),
        currency=(course.currency or "usd").lower(),
        success_url=success_url, cancel_url=cancel_url,
        metadata={
            "course_id": str(course.id),
            "user_id": str(current.id),
            "organization_id": str(current.organization_id),
            "source": "ifpi_course_checkout",
        },
    )
    try:
        session = await checkout.create_checkout_session(checkout_req)
    except Exception as e:  # noqa: BLE001
        logger.exception("stripe create_checkout_session failed")
        raise HTTPException(status_code=502,
                            detail=f"Stripe checkout failed: {e}")

    txn = PaymentTransaction(
        organization_id=current.organization_id,
        user_id=current.id,
        product_type="course", product_id=course.id,
        amount_cents=course.price_cents, currency=course.currency or "usd",
        stripe_session_id=session.session_id,
        status="initiated", payment_status="pending",
        payload={"metadata": checkout_req.metadata,
                 "amount_cents": course.price_cents},
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    return CheckoutSessionOut(
        url=session.url, session_id=session.session_id, transaction_id=txn.id,
    )


@router.get("/checkout/status/{session_id}", response_model=CheckoutStatusOut)
async def get_checkout_status(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Poll Stripe for the payment status of a checkout session and
    fulfil the entitlement if paid. Idempotent — safe to call
    repeatedly from the frontend while it waits for the webhook."""
    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.stripe_session_id == session_id,
        PaymentTransaction.user_id == current.id,
    ).first()
    if not txn:
        raise HTTPException(status_code=404,
                            detail="Payment transaction not found")

    already = txn.fulfilled_at is not None

    checkout = _stripe_checkout(request)
    try:
        cs = await checkout.get_checkout_status(session_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("stripe get_checkout_status failed")
        raise HTTPException(status_code=502,
                            detail=f"Stripe status check failed: {e}")

    # emergentintegrations returns a CheckoutStatusResponse pydantic obj
    status_dict = {
        "status": getattr(cs, "status", None),
        "payment_status": getattr(cs, "payment_status", None),
        "amount_total": getattr(cs, "amount_total", txn.amount_cents),
        "currency": getattr(cs, "currency", txn.currency),
    }
    _fulfill_if_paid(db, txn, status_dict)

    # Re-read entitlement to send back the definitive state
    from services.entitlement_service import EntitlementService
    entitled = EntitlementService(db).has_course_entitlement(
        current.id, txn.product_id)

    return CheckoutStatusOut(
        session_id=session_id,
        status=txn.status,
        payment_status=txn.payment_status,
        amount_cents=txn.amount_cents,
        currency=txn.currency,
        course_id=txn.product_id,
        entitled=entitled,
        already_processed=already,
    )


@webhook_router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook receiver. Idempotent — the poll path and the
    webhook race to fulfill; whichever hits first wins.

    Signature verification is delegated to
    `StripeCheckout.handle_webhook` (uses `STRIPE_WEBHOOK_SECRET` on
    the SDK-managed side)."""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")

    checkout = _stripe_checkout(request)
    try:
        response = await checkout.handle_webhook(body, signature)
    except Exception as e:  # noqa: BLE001
        logger.exception("stripe webhook verify failed")
        raise HTTPException(status_code=400,
                            detail=f"Webhook verification failed: {e}")

    session_id = getattr(response, "session_id", None)
    if not session_id:
        return {"received": True, "note": "no session_id in webhook payload"}

    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.stripe_session_id == session_id,
    ).first()
    if not txn:
        return {"received": True, "note": "no matching transaction"}

    _fulfill_if_paid(db, txn, {
        "status": getattr(response, "event_type", "processed"),
        "payment_status": getattr(response, "payment_status", None),
    })
    return {"received": True, "session_id": session_id,
            "fulfilled": txn.fulfilled_at is not None}
