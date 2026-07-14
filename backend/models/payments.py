"""Payment transaction ledger — one row per Stripe Checkout Session
(Iter 39 P1: Stripe integration).

Every checkout attempt writes a row here BEFORE the redirect to
Stripe, so we always have a full audit trail even if the browser
never reaches the success URL. Rows are updated on the way back via
either the frontend poll or the webhook receiver — whichever hits
first wins (idempotent via `stripe_session_id` uniqueness).

Amount is server-authoritative (read from `Course.price_cents` at
create time). Frontend never sends the amount — prevents price
manipulation at the checkout boundary.
"""
from __future__ import annotations

from sqlalchemy import (
    JSON, Column, DateTime, ForeignKey, Integer, String, Index,
)

from core.database import Base
from ._common import _utcnow


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_txn_org_user", "organization_id", "user_id"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),
                     nullable=False, index=True)
    # What the user was buying. Currently only "course" is supported;
    # kept generic for future (bundle, subscription tier, etc.).
    product_type = Column(String(32), nullable=False, default="course")
    product_id = Column(Integer, nullable=False)  # course_id today
    # Server-authoritative amount at session-creation time.
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False, default="usd")
    # Stripe session id — unique; used as the natural idempotency key
    # when the webhook + the frontend poll race to fulfill the txn.
    stripe_session_id = Column(String(200), nullable=False, unique=True,
                               index=True)
    # Values: `initiated`, `pending`, `paid`, `expired`, `failed`.
    status = Column(String(32), nullable=False, default="initiated",
                    index=True)
    payment_status = Column(String(32), nullable=True)
    # Freeform metadata (Stripe metadata dict, links back to our seams).
    payload = Column(JSON, nullable=False, default=dict, server_default="{}")

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow,
                        nullable=False)
    fulfilled_at = Column(DateTime, nullable=True)
