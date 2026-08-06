"""All SQLAlchemy models for IFPI LMS — domain-split (Iter 34/P3).

Multi-tenant by `organization_id` on every owned row (matches ERP360 pattern).
Designed to work identically on SQLite (dev) and PostgreSQL (prod).

Domain layout (Iter 34 refactor):
  - `_common`      : shared enums + `_utcnow`/`_cuid` helpers
  - `identity`     : Organization, User, roles, tokens, GDPR, Person, Invitation, SSO
  - `learning`     : Course, Slide, Exam, Enrollment, LearningPath, SCORM, xAPI, SlideVersion, SlideComment
  - `certificates` : Certificate, revocation, badges
  - `governance`   : AuditLog, Outbox, ImportJob, Terms, Kiosk, FeatureFlag, ScheduledReport, Notification
  - `integrations` : Webhooks, ApiToken, ApiTokenCall
  - `billing`      : Subscription, BillingEvent, Affiliate*
  - `ai`           : RAG corpus, jobs, ledger, flashcards, tutor sessions
                     (`SourceChunk.embedding` is pgvector-ready — see module)
  - `engagement`   : LiveSession, RSVP, CourseView, SlideView

Every symbol below is re-exported unchanged, so external code that does
`from models import User` keeps working with zero changes.
"""
from __future__ import annotations

# Order matters ONLY insofar as Python module import order — SQLAlchemy
# resolves FK strings + relationships lazily, so cross-domain references
# work regardless. Enums come first so downstream modules can import them.

from ._common import (
    _cuid,
    _utcnow,
    CourseStatus,
    EnrollmentStatus,
    LearningPathStatus,
    LifecycleStage,
    OrganizationStatus,
    QuestionType,
    SlideType,
    SubscriptionStatus,
)
from .identity import (
    AccountDeletionRequest,
    CustomThemePreset,
    EmailVerificationToken,
    Invitation,
    Organization,
    PasswordResetToken,
    Person,
    RefreshToken,
    SsoJtiSeen,
    Erp360SeenEvent,
    ProgressOutbox,
    User,
    UserRole,
)
from .learning import (
    Course,
    CoursePrerequisite,
    CourseSlide,
    Enrollment,
    Exam,
    ExamAttempt,
    ExamQuestion,
    LearningPath,
    LearningPathEnrollment,
    LearningPathItem,
    ScormPackage,
    SlideComment,
    SlideVersion,
    XApiStatement,
)
from .certificates import (
    BadgeTier,
    Certificate,
    CertificateRevocationEvent,
    UserBadge,
)
from .governance import (
    AuditLog,
    FeatureFlag,
    ImportJob,
    KioskSettings,
    Notification,
    OutboxMessage,
    ScheduledReport,
    TermsAcceptance,
    TermsVersion,
)
from .integrations import (
    ApiToken,
    ApiTokenCall,
    WebhookDelivery,
    WebhookSubscription,
)
from .billing import (
    AffiliateCode,
    AffiliateReferral,
    BillingEvent,
    Subscription,
)
from .payments import (
    PaymentTransaction,
)
from .ai import (
    AIJob,
    AITutorMessage,
    AITutorSession,
    AIUsageLedger,
    Flashcard,
    FlashcardReview,
    SourceChunk,
    SourceDocument,
)
from .engagement import (
    CourseRating,
    CourseView,
    LiveSession,
    LiveSessionRsvp,
    SlideView,
    TesterFeedback,
)

__all__ = [
    # helpers
    "_cuid", "_utcnow",
    # enums
    "CourseStatus", "EnrollmentStatus", "LearningPathStatus",
    "LifecycleStage", "OrganizationStatus", "QuestionType", "SlideType",
    "SubscriptionStatus",
    # identity
    "AccountDeletionRequest", "CustomThemePreset", "EmailVerificationToken", "Invitation",
    "Organization", "PasswordResetToken", "Person", "RefreshToken",
    "SsoJtiSeen", "Erp360SeenEvent", "ProgressOutbox", "User", "UserRole",
    # learning
    "Course", "CoursePrerequisite", "CourseSlide", "Enrollment", "Exam",
    "ExamAttempt", "ExamQuestion", "LearningPath",
    "LearningPathEnrollment", "LearningPathItem", "ScormPackage",
    "SlideComment", "SlideVersion", "XApiStatement",
    # certificates
    "BadgeTier", "Certificate", "CertificateRevocationEvent", "UserBadge",
    # governance
    "AuditLog", "FeatureFlag", "ImportJob", "KioskSettings",
    "Notification", "OutboxMessage", "ScheduledReport",
    "TermsAcceptance", "TermsVersion",
    # integrations
    "ApiToken", "ApiTokenCall", "WebhookDelivery", "WebhookSubscription",
    # billing
    "AffiliateCode", "AffiliateReferral", "BillingEvent", "Subscription",
    "PaymentTransaction",
    # ai
    "AIJob", "AITutorMessage", "AITutorSession", "AIUsageLedger",
    "Flashcard", "FlashcardReview", "SourceChunk", "SourceDocument",
    # engagement
    "CourseRating", "CourseView", "LiveSession", "LiveSessionRsvp", "SlideView", "TesterFeedback",
]
