"""Governance — notifications, audit log, outbox, T&Cs, kiosk, feature flags, import jobs, scheduled reports."""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String,
    Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base
from ._common import _utcnow


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


class TermsVersion(Base):
    """A single published version of an organisation's Terms & Conditions."""
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
    """Per-org kiosk config. One row per org."""
    __tablename__ = "kiosk_settings"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"),
                             nullable=False, unique=True, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    idle_timeout_seconds = Column(Integer, default=300, nullable=False)
    unlock_pin_hash = Column(String(200), nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow,
                        nullable=False)


class FeatureFlag(Base):
    """Per-org feature module toggle."""
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


class ScheduledReport(Base):
    """Iter 30p — Per-admin schedulable reports.

    Report types (report_kind):
      - `members_needing_action`
      - `cohort_progress`
      - `certificate_issuance`
      - `enrollment_summary`

    Cadence (cadence): `daily | weekly | monthly`.
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
