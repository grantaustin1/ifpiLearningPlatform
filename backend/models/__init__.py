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
    __table_args__ = (Index("ix_courses_org_status", "organization_id", "status"),)
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
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    slides = relationship("CourseSlide", back_populates="course",
                          cascade="all,delete-orphan", order_by="CourseSlide.order_index")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all,delete-orphan")
    certificates = relationship("Certificate", back_populates="course")


class CourseSlide(Base):
    __tablename__ = "course_slides"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    slide_type = Column(SQLEnum(SlideType), default=SlideType.TEXT)
    media_url = Column(String(500))
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
