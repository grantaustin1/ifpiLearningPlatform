"""ERP360 outbound webhook dispatcher — auto-provisioner.

The generic `WebhookSubscription` table lets any admin add subscribers
manually. For the ERP360 integration we want a canonical, always-there
subscription that:

- Is created automatically when an admin flips
  `integrations.erp360.connected=true` on their org.
- Is pointed at a sentinel `dry-run://erp360` URL until the operator
  configures a real target — so events sign + queue but never leave
  the box. This means the moment ERP360 exposes their inbound
  endpoint, ops PATCH the URL and prior queued events are flushed.
- Uses `IFPI_WEBHOOK_OUTBOUND_SECRET` for signing (matches what
  ERP360 will verify on their side).
- Subscribes to the ERP360-relevant event types only, not `*`.

Idempotent by unique `(organization_id, description="erp360-managed")`
so calling `ensure_erp360_subscription(db, org)` on every PATCH is
safe.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from typing import Optional

from core.config import settings
from sqlalchemy.orm import Session

from models import Organization, WebhookSubscription

logger = logging.getLogger("ifpi.webhooks.erp360")

ERP360_MANAGED_MARKER = "erp360-managed"
DRY_RUN_URL = "dry-run://erp360"

# Events IFPI dispatches TO ERP360 (per IFPI_INTEGRATION_HANDOFF.md §5.2).
ERP360_EVENT_TYPES = [
    "learner.invited",
    "certificate.issued",
    "course.completed",
    "cohort.milestone_reached",
]


def _default_target_url() -> str:
    """Return the ERP360 inbound URL if configured, else a dry-run
    sentinel. Env preference: `ERP360_WEBHOOK_TARGET_URL` (explicit
    inbound URL) > `ERP360_BASE_URL/api/ifpi/webhooks` (conventional) >
    dry-run sentinel."""
    explicit = (os.environ.get("ERP360_WEBHOOK_TARGET_URL") or "").strip()
    if explicit:
        return explicit
    base = (os.environ.get("ERP360_BASE_URL") or "").strip().rstrip("/")
    if base:
        return f"{base}/api/ifpi/webhooks"
    return DRY_RUN_URL


def _default_secret() -> str:
    """Signing secret. Prefer the coordinated
    `IFPI_WEBHOOK_OUTBOUND_SECRET` env; fall back to a locally-generated
    random secret so the subscription still works in single-tenant
    preview (with a warning log)."""
    secret = (settings.webhook_outbound_secret or "").strip()
    if secret:
        return secret
    logger.warning(
        "ERP360 webhook auto-provisioner: IFPI_WEBHOOK_OUTBOUND_SECRET "
        "is unset — generating a per-subscription random secret. Set "
        "the env var and run this provisioner again to sync with the "
        "ERP360 side."
    )
    return secrets.token_urlsafe(48)


def ensure_erp360_subscription(
    db: Session, org: Organization,
) -> WebhookSubscription:
    """Create or update the canonical ERP360-managed subscription for
    this org. Idempotent — safe to call on every PATCH.

    Marker: `description == ERP360_MANAGED_MARKER` identifies the row
    (admins can't reuse that description via the generic /admin/webhooks
    endpoints because we filter it out there).
    """
    sub = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.organization_id == org.id,
            WebhookSubscription.description == ERP360_MANAGED_MARKER,
        )
        .first()
    )

    target = _default_target_url()
    events_json = json.dumps(ERP360_EVENT_TYPES)

    if sub is None:
        sub = WebhookSubscription(
            organization_id=org.id,
            target_url=target,
            events=events_json,
            description=ERP360_MANAGED_MARKER,
            is_active=True,
            secret=_default_secret(),
        )
        db.add(sub)
        db.flush()
        logger.info(
            "erp360.subscription.created org_id=%s target=%s "
            "events=%d",
            org.id, target, len(ERP360_EVENT_TYPES),
        )
    else:
        # Refresh URL + secret so ops changes to env take effect on
        # the next PATCH cycle. Don't clobber a real URL that was set
        # manually via the admin webhook UI — only auto-update the
        # dry-run sentinel.
        if (sub.target_url or "").startswith("dry-run://"):
            sub.target_url = target
        # Always refresh events + activation state.
        sub.events = events_json
        sub.is_active = True
        logger.info(
            "erp360.subscription.updated org_id=%s target=%s",
            org.id, sub.target_url,
        )

    return sub


def deactivate_erp360_subscription(
    db: Session, org: Organization,
) -> Optional[WebhookSubscription]:
    """Called when an admin sets `integrations.erp360.connected=false`.
    We don't delete the row — deactivation preserves the delivery log
    for audit. `is_active=False` short-circuits `emit_event` scanning.
    """
    sub = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.organization_id == org.id,
            WebhookSubscription.description == ERP360_MANAGED_MARKER,
        )
        .first()
    )
    if sub is not None and sub.is_active:
        sub.is_active = False
        logger.info("erp360.subscription.deactivated org_id=%s", org.id)
    return sub