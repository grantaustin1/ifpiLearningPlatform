"""All SQLAlchemy models for IFPI LMS.

Multi-tenant by `organization_id` on every owned row (matches ERP360 pattern).
Designed to work identically on SQLite (dev) and PostgreSQL (production /
ERP360 cluster).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Enum as SQLEnum, Float, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _cuid() -> str:
    return uuid.uuid4().hex


# ── Enums ─────────────────────────────────────────────────────────────
class OrganizationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    TRIAL = "TRIAL"
    SUSPENDED = "SUSPENDED"


class CourseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SlideType(str, enum.Enum):
    TEXT = "TEXT"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    PDF = "PDF"
    SCORM = "SCORM"  # SCORM 1.2 / 2004 package launched via iframe


class QuestionType(str, enum.Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    FILL_IN_BLANK = "FILL_IN_BLANK"
    SHORT_ANSWER = "SHORT_ANSWER"


class EnrollmentStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class SubscriptionStatus(str, enum.Enum):
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"


class LifecycleStage(str, enum.Enum):
    """Mirrors ERP360's Person lifecycle terminology. PROSPECT → LEARNER → ALUMNI."""
    PROSPECT = "PROSPECT"
    LEARNER = "LEARNER"
    ALUMNI = "ALUMNI"


class LearningPathStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


# ── Organization (academy / tenant) ───────────────────────────────────
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    description = Column(Text)
    logo_url = Column(String(500))
    primary_color = Column(String(16), default="#6366f1")
    # Certificate branding (used by services/pdf_certificate_service.py)
    cert_accent_color = Column(String(16))               # falls back to primary_color
    cert_signature_text = Column(String(200))            # e.g. "Frances Moore, CEO"
    cert_signature_image_url = Column(String(500))       # signature PNG/SVG
    cert_footer_text = Column(Text)                      # disclaimer / contact line
    theme_preset = Column(String(40))                    # nullable — e.g. "conservatoire" | "music_school"
    # AI authoring budget (Iter 22 — see docs/AI_AUTHORING_SUITE_ROADMAP.md).
    # Enforced by services/ai_budget_service before every LLM/media dispatch.
    ai_monthly_budget_cents = Column(Integer, default=20000, nullable=False)  # default $200 (Sora cap)
    # Per-tenant SMTP override (nullable — when populated, outbox worker
    # dispatches via this server instead of falling back to the global stub
    # / ERP360 bridge). smtp_password_enc is encrypted at rest with Fernet.
    smtp_host = Column(String(200))
    smtp_port = Column(Integer)
    smtp_username = Column(String(200))
    smtp_password_enc = Column(Text)                     # Fernet-encrypted; never returned to API clients
    smtp_from_email = Column(String(200))
    smtp_from_name = Column(String(200))
    smtp_use_tls = Column(Boolean, default=True)
    # Cohort milestone celebrations (per-tenant tuneable)
    cohort_threshold = Column(Integer, default=75)         # % completion required to fire
    cohort_celebration_webhook_url = Column(Text)          # optional Discord/Slack URL
    # Weekly cohort digest (Monday 09:00 UTC) — predictive nudge for cohorts
    # approaching the threshold + recap of those past it.
    cohort_digest_enabled = Column(Boolean, default=True, nullable=False)
    cohort_digest_last_sent_at = Column(DateTime)
    # Iter 22 — Marketplace opt-in. When true, this org's PUBLISHED courses
    # appear in the cross-tenant public marketplace (/api/catalog, /marketplace).
    # Default true so the seeded IFPI org is discoverable out-of-the-box.
    marketplace_opt_in = Column(Boolean, default=True, nullable=False)
    status = Column(SQLEnum(OrganizationStatus), default=OrganizationStatus.ACTIVE)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    users = relationship("User", back_populates="organization")


# ── User + role ──────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_org_email", "organization_id", "email"),)
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # null for SSO-only users
    name = Column(String(200))
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    last_login_at = Column(DateTime)
    points = Column(Integer, default=0)             # gamification XP
    cohort = Column(String(100), index=True)         # nullable — populated when invited via a cohort batch
    erp360_user_id = Column(Integer, nullable=True, index=True)  # link for SSO
    # Iter 30i — TOTP-based 2FA (RFC 6238). Secret stored Fernet-
    # encrypted alongside SMTP passwords. Enabled_at both marks the
    # user as 2FA-required AND records when they turned it on. Recovery
    # codes are single-use bcrypt-hashed backups (10 issued at setup).
    totp_secret_enc = Column(String(500), nullable=True)
    totp_enabled_at = Column(DateTime, nullable=True)
    totp_recovery_codes = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    organization = relationship("Organization", back_populates="users")
    person = relationship("Person", back_populates="user", uselist=False,
                          cascade="all,delete-orphan")
    user_roles = relationship("UserRole", back_populates="user", cascade="all,delete-orphan")
    enrollments = relationship("Enrollment", back_populates="user", cascade="all,delete-orphan")
    exam_attempts = relationship("ExamAttempt", back_populates="user", cascade="all,delete-orphan")
    certificates = relationship("Certificate", back_populates="user", cascade="all,delete-orphan")
    badges = relationship("UserBadge", back_populates="user", cascade="all,delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all,delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all,delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all,delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="user_roles")


class RefreshToken(Base):
    """Family-tracked refresh tokens. Reuse-of-consumed → treat as compromise."""
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    family_id = Column(String(64), nullable=False, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="refresh_tokens")


# ── Course & slides ──────────────────────────────────────────────────
class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_org_status", "organization_id", "status"),
        UniqueConstraint("organization_id", "title", name="uq_courses_org_title"),
    )
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(80), index=True)
    cover_color = Column(String(32), default="bg-indigo-500")
    cover_image = Column(String(500))
    status = Column(SQLEnum(CourseStatus), default=CourseStatus.DRAFT, index=True)
    passing_score = Column(Integer, default=70)
    duration_minutes = Column(Integer)
    price_cents = Column(Integer, default=0)            # 0 = free
    currency = Column(String(3), default="ZAR")
    display_order = Column(Integer, default=0, index=True)  # catalog ordering
    metadata_json = Column(JSON)                              # {mindmap_layout, ...}
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    slides = relationship("CourseSlide", back_populates="course",
                          cascade="all,delete-orphan", order_by="CourseSlide.order_index")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all,delete-orphan")
    certificates = relationship("Certificate", back_populates="course")


class CourseSlide(Base):
    __tablename__ = "course_slides"
    __table_args__ = (
        UniqueConstraint("course_id", "order_index", name="uq_course_slides_order"),
    )
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    slide_type = Column(SQLEnum(SlideType), default=SlideType.TEXT)
    media_url = Column(String(500))
    narration_url = Column(String(500))       # cached TTS narration (Iter 26)
    narration_voice = Column(String(30))       # last-used voice — for re-runs
    order_index = Column(Integer, default=0)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    course = relationship("Course", back_populates="slides")


# ── Exams ────────────────────────────────────────────────────────────
class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    time_limit_minutes = Column(Integer)
    passing_score = Column(Integer, default=70)
    max_attempts = Column(Integer, default=3)
    randomize = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    questions = relationship("ExamQuestion", back_populates="exam",
                             cascade="all,delete-orphan", order_by="ExamQuestion.order_index")
    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all,delete-orphan")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionType), default=QuestionType.MULTIPLE_CHOICE)
    options = Column(JSON, nullable=True)        # list[str]
    correct_answer = Column(String(500), nullable=False)
    explanation = Column(Text)
    points = Column(Integer, default=1)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    exam = relationship("Exam", back_populates="questions")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (Index("ix_attempts_exam_user", "exam_id", "user_id"),)
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Float, default=0)
    passed = Column(Boolean, default=False)
    answers = Column(JSON, nullable=True)        # dict[question_id->answer]
    started_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    exam = relationship("Exam", back_populates="attempts")
    user = relationship("User", back_populates="exam_attempts")


# ── Enrollments & certificates ───────────────────────────────────────
class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_enroll_user_course"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.IN_PROGRESS)
    progress = Column(Float, default=0.0)
    enrolled_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=True)
    type = Column(String(50), default="COURSE_COMPLETION")
    code = Column(String(40), unique=True, nullable=False, default=_cuid)
    score = Column(Float, nullable=True)
    issued_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="certificates")
    course = relationship("Course", back_populates="certificates")


# ── Gamification ─────────────────────────────────────────────────────
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


# ── Notifications ────────────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_read", "user_id", "is_read"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50))
    title = Column(String(200))
    message = Column(Text)
    link = Column(String(500))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="notifications")


# ── Billing (stub for v1; webhook-driven via ERP360 later) ───────────
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


# ── Person (mirrors ERP360 identity model — separate from User auth) ──
class Person(Base):
    """A person's identity & lifecycle (LEAD → LEARNER → ALUMNI).

    ERP360 has a `Person` table as the central identity entity, distinct from
    the auth-bearing `User`. IFPI mirrors that here — when SSO is enabled,
    `erp360_person_id` links one IFPI Person → one ERP360 Person.

    Cardinality: User 1—1 Person (auto-created with User; can also exist
    without a User in future for invited learners who haven't registered).
    """
    __tablename__ = "persons"
    __table_args__ = (
        Index("ix_persons_org_email", "organization_id", "email"),
        Index("ix_persons_erp", "erp360_person_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(200), nullable=False)
    name = Column(String(200))
    phone = Column(String(50))
    job_title = Column(String(150))
    company = Column(String(200))
    country = Column(String(80))
    lifecycle_stage = Column(SQLEnum(LifecycleStage), default=LifecycleStage.PROSPECT, index=True)
    source = Column(String(50))            # e.g. "self_register", "sso_erp360", "import"
    erp360_person_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="person")


# ── Learning paths (ordered courses with prerequisites) ──────────────
class LearningPath(Base):
    __tablename__ = "learning_paths"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(120), index=True)
    description = Column(Text)
    cover_color = Column(String(32), default="bg-violet-500")
    status = Column(SQLEnum(LearningPathStatus), default=LearningPathStatus.DRAFT, index=True)
    estimated_hours = Column(Integer)
    price_cents = Column(Integer, default=0)
    currency = Column(String(3), default="ZAR")
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    items = relationship("LearningPathItem", back_populates="path",
                         cascade="all,delete-orphan", order_by="LearningPathItem.order_index")
    enrollments = relationship("LearningPathEnrollment", back_populates="path",
                               cascade="all,delete-orphan")


class LearningPathItem(Base):
    """Ordered course in a learning path. `is_required=False` = optional bonus."""
    __tablename__ = "learning_path_items"
    __table_args__ = (UniqueConstraint("path_id", "course_id", name="uq_path_course"),)
    id = Column(Integer, primary_key=True)
    path_id = Column(Integer, ForeignKey("learning_paths.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    order_index = Column(Integer, default=0)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    path = relationship("LearningPath", back_populates="items")
    course = relationship("Course")


class CoursePrerequisite(Base):
    """A course can require another course be completed first. Many-to-many."""
    __tablename__ = "course_prerequisites"
    __table_args__ = (UniqueConstraint("course_id", "prerequisite_course_id",
                                       name="uq_course_prereq"),)
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    prerequisite_course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class LearningPathEnrollment(Base):
    __tablename__ = "learning_path_enrollments"
    __table_args__ = (UniqueConstraint("user_id", "path_id", name="uq_path_enroll"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    path_id = Column(Integer, ForeignKey("learning_paths.id"), nullable=False, index=True)
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.IN_PROGRESS)
    progress = Column(Float, default=0.0)
    enrolled_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    path = relationship("LearningPath", back_populates="enrollments")




# ── Invitations (admin-issued tokens to onboard instructors/admins) ──
class Invitation(Base):
    """Email-based invite. Once accepted, creates a User+Person with the chosen role."""
    __tablename__ = "invitations"
    __table_args__ = (Index("ix_invites_org_email", "organization_id", "email"),)
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(200), nullable=False)
    name = Column(String(200))
    role = Column(String(50), nullable=False)
    cohort = Column(String(100), index=True)         # nullable — propagated to the User on accept
    token = Column(String(64), unique=True, nullable=False, index=True)
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


# ── Outbox: append-only audit of every email we sent (or tried to send) ──
class OutboxMessage(Base):
    """Captures every transactional email. In stub mode, this IS the email log
    (no SMTP sent). In live mode (ERP360 transport), also records the upstream id.
    """
    __tablename__ = "outbox_messages"
    __table_args__ = (Index("ix_outbox_status_created", "status", "created_at"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    to_email = Column(String(200), nullable=False)
    to_name = Column(String(200))
    subject = Column(String(300), nullable=False)
    body_text = Column(Text)
    body_html = Column(Text)
    attachments = Column(JSON, nullable=True)   # [{filename, mime, base64?, url?}]
    template = Column(String(60))               # e.g. "cert_issued", "invitation"
    status = Column(String(20), default="QUEUED", index=True)   # QUEUED, SENT, FAILED, STUB, DEAD_LETTER
    transport = Column(String(20))              # "stub", "erp360"
    transport_message_id = Column(String(120))  # upstream id (when real send happens)
    error = Column(Text)
    attempt_count = Column(Integer, default=0)  # incremented every dispatch attempt
    next_attempt_at = Column(DateTime, nullable=True)  # backoff schedule
    created_at = Column(DateTime, default=_utcnow)
    sent_at = Column(DateTime, nullable=True)


# ── Slide comments (discussion threads under each slide) ─────────────
class SlideComment(Base):
    __tablename__ = "slide_comments"
    __table_args__ = (Index("ix_comments_slide_created", "slide_id", "created_at"),)
    id = Column(Integer, primary_key=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("slide_comments.id"), nullable=True, index=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)


# ── Audit log: append-only record of admin mutations ──
class AuditLog(Base):
    """Append-only log of admin actions for compliance + forensic review.

    Captures: who (actor_user_id), did what (action), to what (target_type +
    target_id), with what payload (metadata JSON), and when. Never UPDATEd
    or DELETEd in normal operation. Scoped to organisation_id for tenant
    isolation."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_actor_created", "actor_user_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    target_type = Column(String(60))
    target_id = Column(String(80))
    audit_metadata = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=_utcnow, index=True)


# ── Outgoing webhooks (HMAC-signed events to ERP360 et al.) ──────────
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


# ── Bulk import jobs (tracks long-running content migrations) ────────
class ImportJob(Base):
    """Status row for one bulk content import. Workers UPDATE this as they
    progress so the admin UI can poll for live progress + error reports."""
    __tablename__ = "import_jobs"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_type = Column(String(50), nullable=False)  # BULK_COURSE | FULL_MIGRATION
    source_path = Column(String(500))
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    # PENDING → RUNNING → COMPLETED | FAILED | PARTIAL
    total_items = Column(Integer, default=0, nullable=False)
    processed_items = Column(Integer, default=0, nullable=False)
    failed_items = Column(Integer, default=0, nullable=False)
    results = Column(JSON)        # {courses:[…], exams:[…], errors:[…]}
    error_log = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow, nullable=False)



# ── SSO replay protection (multi-process safe) ───────────────────────
class SsoJtiSeen(Base):
    """One row per inbound SSO token jti we've seen. Replaces the in-memory
    `_SEEN_JTI` dict so replay protection works across multiple FastAPI
    workers / pods. A small background sweeper purges rows older than the
    replay TTL (10 min by default)."""
    __tablename__ = "sso_jti_seen"
    __table_args__ = (Index("ix_sso_jti_seen_at", "seen_at"),)
    jti = Column(String(120), primary_key=True)
    seen_at = Column(DateTime, default=_utcnow, nullable=False)



# ── SCORM packages (Iter 18) ─────────────────────────────────────────
class ScormPackage(Base):
    """One row per uploaded SCORM package. The actual ZIP contents are
    extracted to disk under STORAGE_PATH/scorm/<org>/<uuid>/ and served as
    static files. `launch_url` is the public URL of the entry HTML.

    Linked to a Course (1—1) so a course can launch a SCORM payload as a
    slide alongside normal TEXT/VIDEO slides.
    """
    __tablename__ = "scorm_packages"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id"), nullable=True, index=True)
    manifest_title = Column(String(300))
    launch_url = Column(String(800), nullable=False)
    scorm_version = Column(String(16))           # "1.2" | "2004" | "unknown"
    package_dir = Column(String(800), nullable=False)  # absolute or storage key root
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=_utcnow, nullable=False)


class XApiStatement(Base):
    """xAPI (Tin Can) statement receiver — stores incoming statements for
    audit + completion-tracking. Minimal viable LRS: we store the raw
    statement JSON and surface common fields for indexing.
    """
    __tablename__ = "xapi_statements"
    __table_args__ = (
        Index("ix_xapi_org_user_stored", "organization_id", "user_id", "stored_at"),
        Index("ix_xapi_verb_stored", "verb", "stored_at"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_email = Column(String(200), index=True)
    verb = Column(String(120), nullable=False)    # e.g. "http://adlnet.gov/expapi/verbs/completed"
    object_id = Column(String(500))               # iri of the activity
    result = Column(JSON)                          # {score, success, completion, …}
    raw = Column(JSON, nullable=False)            # full original statement
    stored_at = Column(DateTime, default=_utcnow, nullable=False)


# ── Slide versioning (Iter 19) ───────────────────────────────────────
class SlideVersion(Base):
    """Immutable snapshot of a CourseSlide at the moment of save. Created on
    every content/title/media_url change so admins can roll back accidental
    edits. The latest live row stays in `course_slides`; this table is
    append-only history.
    """
    __tablename__ = "slide_versions"
    __table_args__ = (Index("ix_slide_versions_slide_ver", "slide_id", "version_number"),)
    id = Column(Integer, primary_key=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    slide_type = Column(String(20))               # store as string for forward-compat
    media_url = Column(String(500))
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    change_summary = Column(String(200))          # optional admin note
    created_at = Column(DateTime, default=_utcnow, nullable=False)



# ── API tokens (Iter 21 — programmatic auth for external integrations) ──
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


# ── AI authoring suite shared infra (Iter 22 — see docs/AI_AUTHORING_SUITE_ROADMAP.md) ──

class SourceDocument(Base):
    """Per-org reference material — PDFs, DOCXs, URLs scraped by deep-research.
    Used as the retrieval corpus for the source-grounded AI tutor. Full-text
    plus per-chunk embeddings (see `SourceChunk`) enable semantic search."""
    __tablename__ = "source_documents"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    title = Column(String(300), nullable=False)
    source_type = Column(String(20), nullable=False)     # PDF | DOCX | URL | RESEARCH_NOTE | MANUAL
    original_url = Column(String(800))                    # populated when scraped from URL
    storage_key = Column(String(400))                     # storage_service key of raw file
    extracted_text = Column(Text)                         # plain-text — the RAG input
    metadata_json = Column(JSON)                          # {authors, published_date, checksum, page_count}
    chunk_count = Column(Integer, default=0, nullable=False)
    embedded_at = Column(DateTime)                        # nullable — set once embeddings finished
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class SourceChunk(Base):
    """Retrieval-ready ~800-token chunk of a SourceDocument, with a vector
    embedding stored as raw JSON list[float]. No pgvector needed at MVP
    scale (<10k chunks/org)."""
    __tablename__ = "source_chunks"
    __table_args__ = (Index("ix_chunk_doc_ord", "document_id", "chunk_index"),)
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("source_documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(JSON)                              # list[float] — 1536 dims (OpenAI ada-2)
    token_count = Column(Integer)


class AIJob(Base):
    """Async LLM/media dispatch — mirrors the ImportJob pattern (Iter 16).
    A background worker will poll `status=PENDING` and dispatch by job_type.
    """
    __tablename__ = "ai_jobs"
    __table_args__ = (Index("ix_ai_jobs_org_status", "organization_id", "status"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    job_type = Column(String(40), nullable=False, index=True)
    # TUTOR_ANSWER | DEEP_RESEARCH | AUTO_QUIZ | FLASHCARDS | VIDEO_OVERVIEW
    # TTS_NARRATION | MIND_MAP | INFOGRAPHIC | PPTX_EXPORT
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    input_json = Column(JSON)
    output_json = Column(JSON)
    artefact_url = Column(String(600))
    cost_cents = Column(Integer, default=0, nullable=False)
    error_log = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class AIUsageLedger(Base):
    """Per-call cost tracking. Aggregated per (org, billing_month) by
    services/ai_budget_service to enforce Organization.ai_monthly_budget_cents.
    """
    __tablename__ = "ai_usage_ledger"
    __table_args__ = (Index("ix_ai_usage_org_month", "organization_id", "billing_month"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("ai_jobs.id"), nullable=True)
    provider = Column(String(30), nullable=False)         # claude | openai | gemini | sora | tavily
    model = Column(String(60))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_cents = Column(Integer, default=0, nullable=False)
    billing_month = Column(String(7), nullable=False)     # "2026-02"
    created_at = Column(DateTime, default=_utcnow, nullable=False)


# ── API token analytics (Iter P2 — 30-day request chart) ───────────
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


class Flashcard(Base):
    """One AI-generated flashcard. Belongs to a course (org-scoped via that
    course). `source_chunk_ids` records provenance so we can show citations
    on the review UI + guarantee no hallucinated cards enter the pack."""
    __tablename__ = "flashcards"
    __table_args__ = (
        Index("ix_flashcards_org_course", "organization_id", "course_id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id"), nullable=True)
    front = Column(String(500), nullable=False)          # question / prompt
    back = Column(Text, nullable=False)                    # answer
    hint = Column(String(300))
    difficulty = Column(Integer, default=2, nullable=False)  # 1-easy .. 5-hard
    tags = Column(JSON)                                     # list[str]
    generated_by_ai = Column(Boolean, default=True, nullable=False)
    source_chunk_ids = Column(JSON)                        # list[int] — provenance
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class FlashcardReview(Base):
    """Learner-side SM-2 spaced-repetition state. One row per (user, card)
    — first review INSERTs it, subsequent reviews UPDATE. Learners see cards
    where `next_review_at <= now`.
    """
    __tablename__ = "flashcard_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "flashcard_id", name="uq_review_user_card"),
        Index("ix_reviews_user_next", "user_id", "next_review_at"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    ease_factor = Column(Float, default=2.5, nullable=False)   # SM-2 EF
    interval_days = Column(Integer, default=0, nullable=False)  # days until next review
    repetitions = Column(Integer, default=0, nullable=False)   # consecutive successful reps
    next_review_at = Column(DateTime, nullable=False)
    last_quality = Column(Integer)                              # last 0-5 rating
    last_reviewed_at = Column(DateTime)
    review_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)



# ═════════════════════════════════════════════════════════════════════
# Iter 30l — T&Cs versions + acceptances, per-org kiosk settings,
# per-org feature-module flags.
# ═════════════════════════════════════════════════════════════════════


class TermsVersion(Base):
    """A single published version of an organisation's Terms & Conditions.

    Versions are additive: publishing a new version supersedes the
    previous `current=True` row (a trigger below flips it). Body is
    markdown; frontend renders + shows a required "I accept" gate the
    first time a user encounters a fresh version.
    """
    __tablename__ = "terms_versions"
    __table_args__ = (
        Index("ix_terms_org_version", "organization_id", "version"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    version = Column(String(32), nullable=False)  # e.g. "1.0", "2024-Q3"
    title = Column(String(255), nullable=False, default="Terms of Service")
    body_markdown = Column(Text, nullable=False, default="")
    is_current = Column(Boolean, nullable=False, default=False, index=True)
    published_by_user_id = Column(Integer, ForeignKey("users.id"))
    published_at = Column(DateTime, nullable=False, default=_utcnow)


class TermsAcceptance(Base):
    """One row per (user, version). Immutable ledger."""
    __tablename__ = "terms_acceptances"
    __table_args__ = (
        UniqueConstraint("user_id", "terms_version_id", name="uq_terms_ack"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    terms_version_id = Column(Integer, ForeignKey("terms_versions.id"),
                              nullable=False, index=True)
    accepted_at = Column(DateTime, nullable=False, default=_utcnow)
    ip_address = Column(String(45))     # IPv4/IPv6 for audit
    user_agent = Column(String(500))


class KioskSettings(Base):
    """Per-org kiosk config. One row per org (nullable — orgs without a
    row default to sensible values)."""
    __tablename__ = "kiosk_settings"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, unique=True, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    # Idle lock timeout in seconds (0 = never lock)
    idle_timeout_seconds = Column(Integer, default=300, nullable=False)
    # Optional PIN (bcrypt-hashed) required to unlock the kiosk. When
    # NULL the user must re-enter password.
    unlock_pin_hash = Column(String(200), nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow,
                        nullable=False)


class FeatureFlag(Base):
    """Per-org feature module toggle. Missing row = default (usually ON).
    This is a stopgap for granular billing / progressive rollout —
    NOT a full LaunchDarkly-style targeting engine."""
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("organization_id", "flag_key", name="uq_flag_org_key"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    flag_key = Column(String(80), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    note = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow,
                        nullable=False)



# ═════════════════════════════════════════════════════════════════════
# Iter 30m — AI Tutor v1 (learner-facing course chat).
# Reuses SourceDocument + SourceChunk + embedding_service for retrieval.
# ═════════════════════════════════════════════════════════════════════


class AITutorSession(Base):
    """One conversation with the AI tutor. Keyed to (user, course) —
    persisted so learners can resume mid-chat."""
    __tablename__ = "ai_tutor_sessions"
    __table_args__ = (
        Index("ix_tutor_session_user_course",
              "user_id", "course_id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False,
                     index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"),
                       nullable=True, index=True)
    title = Column(String(200), nullable=False, default="New chat")
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    last_message_at = Column(DateTime, default=_utcnow, nullable=False)


class AITutorMessage(Base):
    """One turn (either user or assistant). Assistant turns carry a JSON
    `citations` list: `[{chunk_id, document_id, document_title, snippet, score}]`.
    """
    __tablename__ = "ai_tutor_messages"
    __table_args__ = (
        Index("ix_tutor_msg_session", "session_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer,
                        ForeignKey("ai_tutor_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    role = Column(String(12), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)    # list[dict] on assistant turns
    tokens_prompt = Column(Integer, nullable=True)
    tokens_completion = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)




class ScheduledReport(Base):
    """Iter 30p — Per-admin schedulable reports.

    Report types (report_kind):
      - `members_needing_action`
      - `cohort_progress`
      - `certificate_issuance`
      - `enrollment_summary`

    Cadence (cadence): `daily | weekly | monthly`. Delivery is via the
    existing outbox_worker Monday-morning tick — we generate + queue the
    email into `outbox_messages` when the next_run_at cursor is reached.
    """
    __tablename__ = "scheduled_reports"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"),
                                nullable=False, index=True)
    report_kind = Column(String(50), nullable=False)
    cadence = Column(String(20), nullable=False)  # daily/weekly/monthly
    recipient_emails = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=False, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow,
                        nullable=False)



# ═════════════════════════════════════════════════════════════════════
# Iter 30s — Affiliate / Referral program.
# ═════════════════════════════════════════════════════════════════════


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



# ── Live Sessions (Iter 22) ──────────────────────────────────────────
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
