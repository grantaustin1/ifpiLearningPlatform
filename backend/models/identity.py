"""Identity domain — organisations, users, roles, auth tokens, GDPR.

Row-level tenancy is via `organization_id` on every downstream table.
"""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base
from ._common import (
    LifecycleStage, OrganizationStatus, _utcnow,
)


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
    # Prospect nurturing — nudge campaign signups who haven't started
    nurture_enabled = Column(Boolean, default=False, server_default="0")
    nurture_days = Column(Integer, default=3, server_default="3")
    nurture_message = Column(Text, nullable=True)
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
    marketplace_opt_in = Column(Boolean, default=True, nullable=False)
    # Iter 25 — Subscription URL secret version. Bumping this (via
    # POST /api/live-sessions/subscribe-url/rotate) invalidates every
    # outstanding calendar-subscription URL scoped to this org, WITHOUT
    # touching JWT_SECRET (which would log out every active user).
    subscription_secret_version = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(OrganizationStatus), default=OrganizationStatus.ACTIVE)
    # §7.4 — Per-org integration state (agreed 2026-07). Replaces the
    # global `SSO_ENABLED` env flag for the ERP360 bolt-on. Global env
    # remains a master feature-switch; per-org state controls WHICH orgs
    # participate. Shape:
    #   {
    #     "erp360": {
    #       "connected": bool,
    #       "org_slug": str,           # ERP360-side slug used in payloads
    #       "sso_enabled": bool,       # allow SSO for this org
    #       "billing_mode": "native_stripe" | "erp360",
    #       "connected_at": iso8601,   # audit
    #     }
    #   }
    # Handlers MUST resolve users only within the org whose ERP360 slug
    # matches `payload.org_slug` — never match standalone-org users by
    # email collision. See ERP360_BOLT_ON_WORK_LIST §7.4.
    integrations = Column(JSON, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    users = relationship("User", back_populates="organization")

    # ── §7.4 helpers ────────────────────────────────────────────────
    @property
    def erp360_settings(self) -> dict:
        """Convenience view — never returns None."""
        return (self.integrations or {}).get("erp360", {}) or {}

    @property
    def is_erp360_connected(self) -> bool:
        return bool(self.erp360_settings.get("connected"))

    @property
    def erp360_org_slug(self) -> str | None:
        """ERP360-side slug used in webhook payloads. Falls back to our
        own `slug` so single-tenant preview setups don't need explicit
        configuration."""
        return self.erp360_settings.get("org_slug") or self.slug

    @property
    def erp360_sso_enabled(self) -> bool:
        """True if this org accepts ERP360 SSO. Falls back to connected
        state so a freshly-connected org gets SSO by default."""
        s = self.erp360_settings
        return bool(s.get("sso_enabled", s.get("connected", False)))


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
    # Iter 27 — streak-break nudge dedup (dont email twice for same lapse)
    streak_nudge_last_sent_at = Column(DateTime, nullable=True)
    # Iter 31 — user-level weekly streak digest opt-out (default True)
    streak_digest_enabled = Column(Boolean, nullable=False, default=True,
                                   server_default="1")
    # Iter 32 — force password change on next login (foot-gun guard for
    # seeded admin@ifpi.org). Set to True on the seed row so shipping
    # with `admin123` becomes impossible. Cleared by the change-password
    # endpoint once the user picks a new one.
    must_change_password = Column(Boolean, nullable=False, default=False,
                                  server_default="0")
    # Iter 33 — GDPR compliance columns.
    # `email_verified_at` is NULL until the user clicks the verification
    # link. Sensitive actions (e.g. becoming an instructor, publishing a
    # course to the marketplace) SHOULD gate on this — see
    # routers/auth.py:verify_email + services/auth_service.py.
    email_verified_at = Column(DateTime, nullable=True)
    # `deleted_at` — GDPR Right to Erasure. We soft-delete + anonymise
    # rather than hard-delete because certificates, exam attempts, and
    # audit records reference this row via foreign keys. Anonymisation
    # replaces email with `deleted-<userid>@anon.invalid` and name
    # with "Deleted User". The row itself remains for referential
    # integrity, is_active=False, password_hash=None.
    deleted_at = Column(DateTime, nullable=True)
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


class CustomThemePreset(Base):
    """Org-defined theme preset (admin console → Settings → Branding).

    Built-in presets live in `services/theme_presets.py`; this table holds
    per-academy custom presets. Both are merged by GET /api/organization/themes.
    """
    __tablename__ = "custom_theme_presets"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_custom_theme_org_slug"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    slug = Column(String(80), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(300))
    primary_color = Column(String(16), nullable=False, default="#6366f1")
    cert_accent_color = Column(String(16), nullable=False, default="#6366f1")
    cert_signature_text_suggestion = Column(String(200))
    cert_footer_text_suggestion = Column(Text)
    cover_color = Column(String(40), default="bg-indigo-500")
    created_at = Column(DateTime, default=_utcnow)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    # §7.3 — Source-of-truth marker. `ifpi_native` roles (INSTRUCTOR,
    # cohort assignments, native-side admin grants) MUST survive every
    # inbound ERP360 `role_changed` webhook. `erp360` roles are managed
    # exclusively by the ERP360 receiver (`_replace_roles`) — that path
    # scopes its DELETE to source='erp360' so native grants are never
    # clobbered. Existing rows default to `ifpi_native` (safe assumption
    # — pre-§7.3 the receiver did full rewrites, but no ERP360-sourced
    # rows actually landed for real users; the one live event was a
    # noop_unknown_user). See ERP360_BOLT_ON_WORK_LIST §7.3.
    source = Column(String(20), nullable=False, default="ifpi_native",
                    server_default="ifpi_native", index=True)
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


class PasswordResetToken(Base):
    """Iter 32 — Email-delivered password-reset tokens.

    Row is created by POST /api/auth/forgot-password. Only the SHA-256
    hash of the token is stored — the raw value only ever exists in the
    outgoing email. Single-use: `used_at` gets stamped by
    /api/auth/reset-password and any further attempts 400.
    """
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    requested_ip = Column(String(45), nullable=True)  # audit trail
    created_at = Column(DateTime, default=_utcnow)


class EmailVerificationToken(Base):
    """Iter 33 — Email-verification tokens issued at signup and via
    the resend endpoint. Same shape/semantics as PasswordResetToken —
    single-use, 24-hour TTL, only the SHA-256 hash is persisted."""
    __tablename__ = "email_verification_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class AccountDeletionRequest(Base):
    """Iter 33 — GDPR Right to Erasure two-step confirmation.

    User POSTs to /api/user/me/delete-request → row created with a
    hashed 6-digit confirmation code, emailed to them. User then
    DELETEs to /api/user/me with the code → this row is stamped
    `confirmed_at` and the User row is anonymised.
    """
    __tablename__ = "account_deletion_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    requested_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


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


class SsoJtiSeen(Base):
    """One row per inbound SSO token jti we've seen. Replaces the in-memory
    `_SEEN_JTI` dict so replay protection works across multiple FastAPI
    workers / pods. A small background sweeper purges rows older than the
    replay TTL (10 min by default)."""
    __tablename__ = "sso_jti_seen"
    __table_args__ = (Index("ix_sso_jti_seen_at", "seen_at"),)
    jti = Column(String(120), primary_key=True)
    seen_at = Column(DateTime, default=_utcnow, nullable=False)


class Erp360SeenEvent(Base):
    """Idempotency store for inbound ERP360 webhook events (§6.4).

    ERP360 may re-deliver the same `event_id` (retry after timeout, manual
    re-queue of a dead-letter, network hiccup). This table gives us a
    replica-safe dedup key that survives restart and scale-out — replaces
    the in-memory `_SEEN_EVENT_IDS` dict.

    Rows are keyed on `event_id` (uuid from `X-ERP360-Event-Id`). A
    background sweeper purges rows older than the retention window
    (default 30 days) to keep the table bounded.
    """
    __tablename__ = "erp360_seen_events"
    __table_args__ = (Index("ix_erp360_seen_events_at", "received_at"),)
    event_id = Column(String(120), primary_key=True)
    received_at = Column(DateTime, default=_utcnow, nullable=False)


class ProgressOutbox(Base):
    """Iter 38 Phase B — Postgres outbox for decoupled progress writes.

    Under 10× traffic, learners clicking through slides generate a
    firehose of `SlideView` inserts. Doing them synchronously ties up
    web workers on lock contention (unique constraint on (slide, user,
    day) can serialize). The outbox splits this into two paths:

      1. **Enqueue (fast)**: web worker inserts one small row here,
         returns 202 to the learner immediately.
      2. **Process (background)**: a worker polls `pending` rows with
         `SELECT ... FOR UPDATE SKIP LOCKED LIMIT N` (Postgres 9.5+),
         performs the actual `SlideView` insert, marks the row `done`.

    Uses a Postgres-friendly locking pattern that also works on SQLite
    (falls back to unlocked SELECT — safe on single-writer). Retries
    failed rows up to `max_attempts` (default 5) with exponential
    backoff via `next_attempt_at`.
    """
    __tablename__ = "progress_outbox"
    __table_args__ = (
        Index("ix_progress_outbox_pending", "status", "next_attempt_at"),
    )
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)  # 'slide_view' | 'lesson_complete' | ...
    payload_json = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending",
                    server_default="pending")  # pending | processing | done | failed
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    next_attempt_at = Column(DateTime, default=_utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)


class CampaignLink(Base):
    """Multi-use public signup link for prospect acquisition campaigns."""
    __tablename__ = "campaign_links"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(40), unique=True, nullable=False, index=True)
    auto_enroll_course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    signup_count = Column(Integer, default=0, nullable=False, server_default="0")
    is_active = Column(Boolean, default=True, nullable=False, server_default="1")
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)


class CampaignSignup(Base):
    """One row per campaign-link signup — carries UTM attribution and
    nurture state."""
    __tablename__ = "campaign_signups"
    id = Column(Integer, primary_key=True, index=True)
    campaign_link_id = Column(Integer, ForeignKey("campaign_links.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    utm_source = Column(String(120), nullable=True)
    utm_medium = Column(String(120), nullable=True)
    utm_campaign = Column(String(120), nullable=True)
    nudged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
