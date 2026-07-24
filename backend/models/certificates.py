"""Certificates + gamification (badges)."""
from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Float, Index, Integer, String,
    Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base
from ._common import _cuid, _utcnow


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=True)
    # Iter 27 — attach cert to a live session for attendance certs
    live_session_id = Column(Integer, ForeignKey("live_sessions.id"),
                             nullable=True, index=True)
    type = Column(String(50), default="COURSE_COMPLETION")
    code = Column(String(40), unique=True, nullable=False, default=_cuid)
    score = Column(Float, nullable=True)
    issued_at = Column(DateTime, default=_utcnow)
    # Iter 29 — Revocation
    revoked_at = Column(DateTime, nullable=True, index=True)
    revoked_reason = Column(String(255), nullable=True)

    user = relationship("User", back_populates="certificates")
    course = relationship("Course", back_populates="certificates")


class CertificateRevocationEvent(Base):
    """Iter 30 — Audit trail for cert revocation actions."""
    __tablename__ = "certificate_revocation_events"
    id = Column(Integer, primary_key=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"),
                            nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"),
                           nullable=False, index=True)
    action = Column(String(20), nullable=False)  # REVOKE | UNREVOKE
    reason = Column(String(255), nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True,
                         default=_utcnow)


class BadgeTier(Base):
    """Per-organization configurable badge ladder.

    Each row defines one tier. `slug` is the durable identifier the
    gamification service references when awarding (FIRST_ENROLLMENT etc.).
    `threshold_xp` is informational/sort-only — actual award triggers live
    in code (course-completion, perfect-score, etc.) and reference by slug.
    `order_index` drives display order (admin drag-reorder).
    """
    __tablename__ = "badge_tiers"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_badge_tier_slug"),
        Index("ix_badge_tier_org_order", "organization_id", "order_index"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    slug = Column(String(50), nullable=False)
    label = Column(String(100), nullable=False)
    emoji = Column(String(8), default="🏅")
    description = Column(Text)
    threshold_xp = Column(Integer, default=0)
    order_index = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge", name="uq_user_badge"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge = Column(String(50), nullable=False)
    earned_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="badges")
