"""All Pydantic schemas. One module to keep boilerplate minimal — split later if it grows."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: Optional[str] = None
    organization_id: int
    roles: List[str] = []
    points: int = 0


class LoginResponse(BaseModel):
    access_token: Optional[str] = None      # omitted in cookie-only mode
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# ── 2FA (TOTP) ───────────────────────────────────────────────────────
class TwoFactorChallenge(BaseModel):
    """Returned instead of a LoginResponse when the user has 2FA enabled.
    Client shows a 6-digit code prompt and POSTs to /api/auth/2fa/challenge
    with the challenge_id + code (or a recovery code)."""
    requires_2fa: bool = True
    challenge_id: str
    expires_in: int      # seconds


class TOTPSetupIn(BaseModel):
    """Body for /api/auth/2fa/setup — client must resend the secret it
    received in /setup along with a code from their authenticator to
    confirm they scanned the QR correctly before we persist."""
    secret: str
    code: str = Field(min_length=6, max_length=6)


class TOTPDisableIn(BaseModel):
    password: str
    code: str  # 6-digit TOTP OR 9-char recovery code


class TOTPChallengeIn(BaseModel):
    challenge_id: str
    code: str  # TOTP OR recovery code


# ── Course ───────────────────────────────────────────────────────────
class SlideIn(BaseModel):
    title: str
    content: Optional[str] = ""
    slide_type: str = "TEXT"
    media_url: Optional[str] = None
    order_index: Optional[int] = None
    is_required: bool = True


class SlideOut(SlideIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    narration_url: Optional[str] = None
    narration_voice: Optional[str] = None


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    passing_score: int = 70
    duration_minutes: Optional[int] = None
    price_cents: int = 0
    currency: str = "ZAR"
    status: str = "DRAFT"


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    passing_score: Optional[int] = None
    duration_minutes: Optional[int] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    cover_color: Optional[str] = None


class CourseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    cover_color: str
    status: str
    duration_minutes: Optional[int] = None
    price_cents: int = 0
    currency: str = "ZAR"
    slide_count: int = 0
    enrollment_count: int = 0
    created_at: datetime
    mindmap_thumbnail_svg: Optional[str] = None  # Iter 30b


class CourseDetail(CourseSummary):
    passing_score: int
    slides: List[SlideOut] = []


# ── Exam ─────────────────────────────────────────────────────────────
class QuestionIn(BaseModel):
    question_text: str
    question_type: str = "MULTIPLE_CHOICE"
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: Optional[str] = None
    points: int = 1
    order_index: int = 0


class QuestionOut(QuestionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: Optional[int] = None
    time_limit_minutes: Optional[int] = None
    passing_score: int = 70
    max_attempts: int = 3
    randomize: bool = False
    is_published: bool = False


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    passing_score: Optional[int] = None
    max_attempts: Optional[int] = None
    randomize: Optional[bool] = None
    is_published: Optional[bool] = None


class ExamSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str] = None
    course_id: Optional[int] = None
    time_limit_minutes: Optional[int] = None
    passing_score: int
    max_attempts: int
    is_published: bool
    question_count: int = 0
    attempt_count: int = 0
    created_at: datetime


class ExamDetail(ExamSummary):
    questions: List[QuestionOut] = []
    user_attempt_count: int = 0


class AttemptSubmit(BaseModel):
    answers: dict[str, str]              # {question_id: answer_string}


class AttemptResult(BaseModel):
    attempt_id: int
    score: float
    passed: bool
    xp_earned: int = 0
    badges_earned: List[str] = []


# ── Enrollment ───────────────────────────────────────────────────────
class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    course_title: str
    status: str
    progress: float
    enrolled_at: datetime
    completed_at: Optional[datetime] = None


# ── Certificate ──────────────────────────────────────────────────────
class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    type: str
    course_title: Optional[str] = None
    issued_at: datetime
    score: Optional[float] = None


# ── AI Builder ───────────────────────────────────────────────────────
class AIBuilderRequest(BaseModel):
    topic: str = Field(min_length=2)
    description: Optional[str] = ""
    num_slides: int = Field(default=5, ge=1, le=20)
    include_quiz: bool = True
    num_questions: int = Field(default=5, ge=1, le=20)


class AIBuilderSlide(BaseModel):
    title: str
    content: str
    slide_type: str = "TEXT"
    order_index: int


class AIBuilderQuestion(BaseModel):
    question_text: str
    question_type: str = "MULTIPLE_CHOICE"
    options: List[str]
    correct_answer: str
    explanation: str = ""
    points: int = 1
    order_index: int


class AIBuilderResponse(BaseModel):
    slides: List[AIBuilderSlide]
    questions: List[AIBuilderQuestion] = []


# ── Billing ──────────────────────────────────────────────────────────
class SubscribeRequest(BaseModel):
    course_id: int


class SubscribeResponse(BaseModel):
    subscription_id: int
    status: str
    checkout_url: Optional[str] = None
    is_stub: bool = False
    message: str


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_code: str
    course_id: Optional[int] = None
    status: str
    amount_cents: int
    currency: str
    next_billing_date: Optional[date] = None
    created_at: datetime


# ── Notifications ────────────────────────────────────────────────────
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: Optional[str]
    title: Optional[str]
    message: Optional[str]
    link: Optional[str]
    is_read: bool
    created_at: datetime


# ── Analytics ────────────────────────────────────────────────────────
class AnalyticsOverview(BaseModel):
    total_learners: int
    total_courses: int
    total_enrollments: int
    completion_rate: int
    total_certificates: int
    total_exam_attempts: int
    avg_exam_score: int
    monthly_enrollments: List[dict[str, Any]]
    top_courses: List[dict[str, Any]]
    recent_activity: List[dict[str, Any]]


class LeaderboardEntry(BaseModel):
    user_id: int
    name: Optional[str]
    points: int
    badges: int
    completed: int
