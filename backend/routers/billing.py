"""Subscription billing routes."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import (
    Course, Subscription, User,
)
from schemas import (
    SubscribeRequest, SubscribeResponse, SubscriptionOut,
)
from services.billing_service import BillingService

logger = logging.getLogger(__name__)



# ── Billing ──────────────────────────────────────────────────────────
billing_router = APIRouter(prefix="/api/billing", tags=["Billing"])


@billing_router.post("/subscribe", response_model=SubscribeResponse)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db),
              current: CurrentUser = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current.id).first()
    course = db.query(Course).filter(
        Course.id == body.course_id, Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    result = BillingService(db).subscribe(user, course)
    return SubscribeResponse(**result)


@billing_router.get("/subscriptions", response_model=List[SubscriptionOut])
def my_subscriptions(db: Session = Depends(get_db),
                     current: CurrentUser = Depends(get_current_user)):
    rows = db.query(Subscription).filter(
        Subscription.user_id == current.id,
    ).order_by(Subscription.created_at.desc()).all()
    return rows


@billing_router.post("/webhook")
async def billing_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives ERP360 billing webhooks. Verified via X-Signature header."""
    body = await request.body()
    sig = request.headers.get("X-Signature") or request.headers.get("x-signature")
    svc = BillingService(db)
    if not svc.verify_webhook_signature(body, sig):
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    event_type = data.get("type") or data.get("event_type") or "unknown"
    return svc.handle_event(event_type, data.get("data") or data)


