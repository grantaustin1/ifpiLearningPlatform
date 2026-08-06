"""Webhook subscription management — admin-only CRUD + test ping + delivery log."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import Organization, WebhookDelivery, WebhookSubscription
from services import audit_service
from services.webhook_service import emit_event

router = APIRouter(prefix="/api/admin/webhooks", tags=["Webhooks"])


KNOWN_EVENT_TYPES = [
    "course.completed",
    "certificate.issued",
    "cohort.milestone_reached",
    "learner.invited",
    "user.provisioned",
]


class SubscriptionIn(BaseModel):
    target_url: HttpUrl
    events: list[str] = Field(default_factory=lambda: ["*"])
    description: Optional[str] = Field(default=None, max_length=200)
    is_active: bool = True
    secret: Optional[str] = None  # if omitted on create, we generate one


class SubscriptionOut(BaseModel):
    id: int
    target_url: str
    events: list[str]
    description: Optional[str]
    is_active: bool
    secret: str
    created_at: datetime
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]


def _row_to_out(s: WebhookSubscription) -> dict:
    try:
        evs = json.loads(s.events or "[]")
    except json.JSONDecodeError:
        evs = []
    return {
        "id": s.id, "target_url": s.target_url, "events": evs,
        "description": s.description, "is_active": s.is_active,
        "secret": s.secret, "created_at": s.created_at,
        "last_success_at": s.last_success_at, "last_failure_at": s.last_failure_at,
    }


@router.get("")
def list_subscriptions(db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(WebhookSubscription).filter(
        WebhookSubscription.organization_id == current.organization_id,
    ).order_by(WebhookSubscription.id.desc()).all()
    return {"items": [_row_to_out(r) for r in rows], "known_events": KNOWN_EVENT_TYPES}


@router.post("", status_code=201)
def create_subscription(body: SubscriptionIn, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    org = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    sub = WebhookSubscription(
        organization_id=org.id,
        target_url=str(body.target_url),
        events=json.dumps(body.events or ["*"]),
        description=body.description,
        is_active=body.is_active,
        secret=(body.secret or secrets.token_urlsafe(32)),
    )
    db.add(sub)
    db.flush()
    audit_service.record(db, current, "WEBHOOK_SUBSCRIPTION_CREATED",
        target_type="webhook_subscription", target_id=str(sub.id),
        metadata={"url": sub.target_url, "events": body.events})
    db.commit()
    return _row_to_out(sub)


@router.put("/{sub_id}")
def update_subscription(sub_id: int, body: SubscriptionIn,
                        db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == sub_id,
        WebhookSubscription.organization_id == current.organization_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.target_url = str(body.target_url)
    sub.events = json.dumps(body.events or ["*"])
    sub.description = body.description
    sub.is_active = body.is_active
    if body.secret:
        sub.secret = body.secret
    audit_service.record(db, current, "WEBHOOK_SUBSCRIPTION_UPDATED",
        target_type="webhook_subscription", target_id=str(sub.id),
        metadata={"url": sub.target_url, "events": body.events,
                  "is_active": body.is_active})
    db.commit()
    return _row_to_out(sub)


@router.delete("/{sub_id}", status_code=204)
def delete_subscription(sub_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == sub_id,
        WebhookSubscription.organization_id == current.organization_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    audit_service.record(db, current, "WEBHOOK_SUBSCRIPTION_DELETED",
        target_type="webhook_subscription", target_id=str(sub.id),
        metadata={"url": sub.target_url})
    db.delete(sub)
    db.commit()


@router.post("/{sub_id}/test")
def test_subscription(sub_id: int, db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Fires a `webhook.test` event with a tiny payload so admins can confirm
    the receiver's HMAC verification works before relying on real events."""
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == sub_id,
        WebhookSubscription.organization_id == current.organization_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    # Force-match by emitting an event the sub doesn't filter against: use
    # the same name and temporarily ensure the events list matches.
    payload = {"hello": "from IFPI", "actor": current.email,
               "timestamp": datetime.now(timezone.utc).isoformat()}
    # Use the service directly so we bypass the per-sub event filter:
    from services.webhook_service import sign, _serialise
    import uuid as _uuid
    envelope = {
        "event_type": "webhook.test",
        "event_id": _uuid.uuid4().hex,
        "organization_id": current.organization_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    raw = _serialise(envelope)
    sig = sign(sub.secret, raw)
    delivery = WebhookDelivery(
        subscription_id=sub.id, organization_id=current.organization_id,
        event_type="webhook.test", event_id=envelope["event_id"],
        payload=raw.decode("utf-8"), signature=sig, status="QUEUED",
    )
    db.add(delivery)
    db.flush()
    from services.webhook_service import _attempt
    _attempt(db, delivery, sub)
    audit_service.record(db, current, "WEBHOOK_TEST_FIRED",
        target_type="webhook_subscription", target_id=str(sub.id),
        metadata={"status": delivery.status, "status_code": delivery.status_code,
                  "error": (delivery.error or "")[:200]})
    db.commit()
    return {
        "status": delivery.status, "status_code": delivery.status_code,
        "error": delivery.error,
    }


@router.get("/deliveries")
def list_all_deliveries(
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Recent WebhookDelivery rows across ALL subscriptions in the
    caller's org. Read-only — for ops visibility of the outbound
    stream (especially the ERP360-managed dry-run subscription).

    Filters: `status` (QUEUED, DELIVERED, FAILED, DEAD_LETTER),
             `event_type` (learner.invited, certificate.issued, …).
    Returns joined subscription metadata so ops can tell dry-run
    apart from live at a glance.
    """
    limit = max(1, min(limit, 200))
    q = (
        db.query(WebhookDelivery, WebhookSubscription)
        .join(WebhookSubscription,
              WebhookSubscription.id == WebhookDelivery.subscription_id)
        .filter(WebhookDelivery.organization_id == current.organization_id)
    )
    if status:
        q = q.filter(WebhookDelivery.status == status.upper())
    if event_type:
        q = q.filter(WebhookDelivery.event_type == event_type)
    rows = q.order_by(WebhookDelivery.id.desc()).limit(limit).all()

    return {
        "items": [{
            "id": d.id,
            "subscription_id": s.id,
            "subscription_description": s.description,
            "target_url": s.target_url,
            "is_dry_run": (s.target_url or "").startswith("dry-run://"),
            "event_type": d.event_type,
            "event_id": d.event_id,
            "status": d.status,
            "status_code": d.status_code,
            "attempt_count": d.attempt_count,
            "error": d.error,
            "created_at": d.created_at,
            "delivered_at": d.delivered_at,
        } for d, s in rows],
    }


@router.get("/{sub_id}/deliveries")
def list_deliveries(sub_id: int, limit: int = 20,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == sub_id,
        WebhookSubscription.organization_id == current.organization_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    limit = max(1, min(limit, 100))
    rows = db.query(WebhookDelivery).filter(
        WebhookDelivery.subscription_id == sub.id,
    ).order_by(WebhookDelivery.id.desc()).limit(limit).all()
    return {
        "items": [{
            "id": r.id, "event_type": r.event_type, "event_id": r.event_id,
            "status": r.status, "status_code": r.status_code,
            "attempt_count": r.attempt_count, "error": r.error,
            "created_at": r.created_at, "delivered_at": r.delivered_at,
        } for r in rows],
    }
