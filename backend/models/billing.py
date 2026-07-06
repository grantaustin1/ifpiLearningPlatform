"""Billing — subscriptions, events, affiliate/referral."""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Enum as SQLEnum, ForeignKey,
    Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base
from ._common import SubscriptionStatus, _utcnow


class Subscription(Base):
    """One row per (user, product). Driven by ERP360 webhooks once live."""
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    product_code = Column(String(80), nullable=False)        # e.g. "IFPI_CORE_LP"
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    external_subscription_id = Column(String(100), index=True)   # ERP360 lite-billing profile id
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.INACTIVE, index=True)
    amount_cents = Column(Integer, default=0)
    currency = Column(String(3), default="ZAR")
    next_billing_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="subscriptions")


class BillingEvent(Base):
    """Append-only audit of every billing webhook (success/failure)."""
    __tablename__ = "billing_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    event_type = Column(String(80), nullable=False, index=True)
    external_id = Column(String(100), nullable=True)
    payload = Column(JSON)
    processed_at = Column(DateTime, default=_utcnow)


class AffiliateCode(Base):
    """A referral code owned by an organisation. Sharing the code with a
    new org during signup earns the owner a credit on their next invoice.
    """
    __tablename__ = "affiliate_codes"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    reward_bps = Column(Integer, nullable=False, default=1000)  # 10% default
    cap_credits_cents = Column(Integer, nullable=True)  # per-referral cap
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    note = Column(String(500), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class AffiliateReferral(Base):
    """One row per (code, referred_organization). Status changes are
    tracked via credited_at."""
    __tablename__ = "affiliate_referrals"
    __table_args__ = (
        UniqueConstraint("code_id", "referred_organization_id",
                         name="uq_referral_code_org"),
    )
    id = Column(Integer, primary_key=True)
    code_id = Column(Integer, ForeignKey("affiliate_codes.id"),
                     nullable=False, index=True)
    referred_organization_id = Column(Integer,
                                      ForeignKey("organizations.id"),
                                      nullable=False, index=True)
    signed_up_at = Column(DateTime, default=_utcnow, nullable=False)
    credit_cents = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING",
                    index=True)  # PENDING | CREDITED | REJECTED
    credited_at = Column(DateTime, nullable=True)
    notes = Column(String(500), nullable=True)
