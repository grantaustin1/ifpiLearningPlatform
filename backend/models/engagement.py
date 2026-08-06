"""Engagement — live sessions, marketplace views, slide views."""
from __future__ import annotations

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base
from ._common import _utcnow


class CourseRating(Base):
    """Learner star rating for a completed course (Iter 44)."""
    __tablename__ = "course_ratings"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_rating_user"),
    )
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1..5
    comment = Column(Text)
    hidden_at = Column(DateTime, nullable=True)  # Iter 47 — admin moderation
    reply_text = Column(Text)                    # Iter 48 — academy reply
    reply_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class TesterFeedback(Base):
    """In-app feedback widget submissions (Iter 44 — UAT + beyond)."""
    __tablename__ = "tester_feedback"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    page = Column(String(300))
    category = Column(String(30), default="BUG")  # BUG | IDEA | OTHER
    message = Column(Text, nullable=False)
    status = Column(String(20), default="NEW", nullable=False)  # NEW | REVIEWED
    created_at = Column(DateTime, default=_utcnow)


class LiveSession(Base):
    """A scheduled cohort session hosted on an external meeting provider
    (Zoom/Meet/Teams — admin pastes the join URL). Learners RSVP, and
    admins mark attendance after the event."""
    __tablename__ = "live_sessions"
    __table_args__ = (
        Index("ix_live_sessions_org_start", "organization_id", "start_at"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)  # optional link to a course
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    meeting_url = Column(String(1000), nullable=False)  # BYO — any Zoom/Meet/Teams link
    start_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False, default=60)
    host_name = Column(String(200), nullable=True)
    cohort = Column(String(100), nullable=True, index=True)  # optional cohort filter
    max_attendees = Column(Integer, nullable=True)
    # Iter 23 — Recurrence + reminder support
    recurrence_rule = Column(String(500), nullable=True)  # iCal RRULE string, e.g. "FREQ=WEEKLY;COUNT=8"
    parent_series_id = Column(Integer, ForeignKey("live_sessions.id"), nullable=True, index=True)
    reminder_sent_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)  # Iter 24 — single-occurrence cancel (EXDATE)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    rsvps = relationship("LiveSessionRsvp", back_populates="session",
                         cascade="all,delete-orphan")


class LiveSessionRsvp(Base):
    """Per-learner RSVP + attendance state.
    Status: RSVP → ATTENDED / NO_SHOW / CANCELLED."""
    __tablename__ = "live_session_rsvps"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_rsvp_session_user"),
    )
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("live_sessions.id"),
                        nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),
                     nullable=False, index=True)
    status = Column(String(20), nullable=False, default="RSVP", index=True)
    rsvped_at = Column(DateTime, default=_utcnow, nullable=False)
    attendance_marked_at = Column(DateTime, nullable=True)

    session = relationship("LiveSession", back_populates="rsvps")


class CourseView(Base):
    """A recorded impression on the public marketplace course-detail page.
    Deduped upstream by (course_id, viewer_key, day) so refresh-mashers
    don't inflate the funnel."""
    __tablename__ = "course_views"
    __table_args__ = (
        Index("ix_course_views_course_day", "course_id", "viewed_on_date"),
        UniqueConstraint(
            "course_id", "viewer_key", "viewed_on_date",
            name="uq_course_view_unique_per_day",
        ),
    )
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    # Viewer key: `u:<user_id>` for authed viewers, `a:<anon_hash>` for
    # anon (SHA-256 of IP+UA truncated to 16 hex chars). Never PII on
    # its own — the anon hash cannot be reversed to an identity.
    viewer_key = Column(String(80), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    referrer = Column(String(500), nullable=True)
    viewed_at = Column(DateTime, default=_utcnow, nullable=False)
    # Day-only column for the dedup unique constraint; ISO date string
    # (SQLite-friendly). Stored redundantly so dedup lookups are indexed.
    viewed_on_date = Column(String(10), nullable=False, index=True)


class SlideView(Base):
    """A recorded impression on a course slide inside the player.

    Fired once per (slide, learner, day) — the frontend calls
    `POST /api/courses/{cid}/slides/{sid}/track-view` when a slide
    becomes the active view. Powers the drop-off heatmap on the Course
    Edit funnel panel."""
    __tablename__ = "slide_views"
    __table_args__ = (
        Index("ix_slide_views_course_slide", "course_id", "slide_id"),
        UniqueConstraint(
            "slide_id", "user_id", "viewed_on_date",
            name="uq_slide_view_per_user_per_day",
        ),
    )
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"),
                       nullable=False, index=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id"),
                      nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),
                     nullable=False, index=True)
    viewed_at = Column(DateTime, default=_utcnow, nullable=False)
    viewed_on_date = Column(String(10), nullable=False, index=True)
