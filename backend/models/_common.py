"""Shared enums and helpers for all IFPI SQLAlchemy models.

Kept in a leaf module so every domain file can import from here without
triggering circular imports.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone


def _utcnow() -> datetime:
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


__all__ = [
    "_utcnow", "_cuid",
    "OrganizationStatus", "CourseStatus", "SlideType", "QuestionType",
    "EnrollmentStatus", "SubscriptionStatus", "LifecycleStage",
    "LearningPathStatus",
]
