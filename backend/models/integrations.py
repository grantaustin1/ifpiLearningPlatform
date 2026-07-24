"""Outbound HMAC webhooks, API tokens, per-token call analytics."""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text,
)

from core.database import Base
from ._common import _utcnow


class WebhookSubscription(Base):
    """A target URL that receives HMAC-signed event POSTs.

    `events` is a JSON list of event_type strings (or `["*"]` for all).
    `secret` is shared with the receiver — they reproduce the HMAC-SHA256
    of the raw request body using this secret and reject mismatches.
    """
    __tablename__ = "webhook_subscriptions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    secret = Column(String(120), nullable=False)
    events = Column(Text, nullable=False)  # JSON list
    description = Column(String(200))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    last_success_at = Column(DateTime)
    last_failure_at = Column(DateTime)


class WebhookDelivery(Base):
    """One row per dispatch attempt. Used for retries + audit + UI inspection."""
    __tablename__ = "webhook_deliveries"
    __table_args__ = (Index("ix_webhook_deliveries_next", "next_attempt_at"),)
    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("webhook_subscriptions.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    event_id = Column(String(80), nullable=False)  # uuid for receiver-side dedup
    payload = Column(Text, nullable=False)
    signature = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="QUEUED")
    status_code = Column(Integer)
    attempt_count = Column(Integer, default=0, nullable=False)
    error = Column(Text)
    next_attempt_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    delivered_at = Column(DateTime)


class ApiToken(Base):
    """Long-lived bearer token for server-to-server access. Created by an
    admin via the dashboard; the secret is only revealed at creation time
    (we store a SHA-256 hash + a short prefix for visibility in the UI).

    Scopes are kept simple in v1 — a list of role strings the token can
    assume (e.g. `["LEARNER"]` for an LRS that only fires xAPI statements).
    """
    __tablename__ = "api_tokens"
    __table_args__ = (Index("ix_api_tokens_org_active", "organization_id", "is_active"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)        # human label, e.g. "LRS bridge"
    prefix = Column(String(12), nullable=False, index=True)   # first 8 chars of plaintext, displayed in UI
    token_hash = Column(String(80), nullable=False, unique=True, index=True)
    scopes = Column(JSON)                              # list[str] of role names
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)                      # nullable = no expiry
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class ApiTokenCall(Base):
    """Every HTTP call authenticated with an API token is recorded here.
    Aggregated per-day by the /tokens/analytics endpoint for the chart."""
    __tablename__ = "api_token_calls"
    __table_args__ = (
        Index("ix_token_calls_token_day", "api_token_id", "created_at"),
        Index("ix_token_calls_org_day", "organization_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                              nullable=False, index=True)
    api_token_id = Column(Integer, ForeignKey("api_tokens.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    path = Column(String(300), nullable=False)      # request path, no query
    method = Column(String(10), nullable=False)     # GET / POST / …
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
