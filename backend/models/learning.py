"""Learning domain — courses, slides, exams, enrollments, learning paths."""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum as SQLEnum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base
from ._common import (
    CourseStatus, EnrollmentStatus, LearningPathStatus, QuestionType,
    SlideType, _utcnow,
)


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
    is_featured = Column(Boolean, default=False, nullable=False, server_default="0")  # Iter 42 — admin-picked marketplace featured row
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
    image_position = Column(String(10), default="above")  # above | beside | behind
    media_opacity = Column(Integer, default=100)  # 20-100 (%) for image/video media
    narration_url = Column(String(500))       # cached TTS narration (Iter 26)
    narration_voice = Column(String(30))       # last-used voice — for re-runs
    order_index = Column(Integer, default=0)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    course = relationship("Course", back_populates="slides")


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
    # Iter 53 — set when a miss-rate alert fired; cleared on question edit
    miss_alerted_at = Column(DateTime, nullable=True)
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


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_enroll_user_course"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.IN_PROGRESS)
    progress = Column(Float, default=0.0)
    last_slide_index = Column(Integer, default=0)
    enrolled_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


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


class SlideComment(Base):
    """Discussion thread under each slide."""
    __tablename__ = "slide_comments"
    __table_args__ = (Index("ix_comments_slide_created", "slide_id", "created_at"),)
    id = Column(Integer, primary_key=True)
    slide_id = Column(Integer, ForeignKey("course_slides.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("slide_comments.id"), nullable=True, index=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)


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


class ScormPackage(Base):
    """One row per uploaded SCORM package. The actual ZIP contents are
    extracted to disk under STORAGE_PATH/scorm/<org>/<uuid>/ and served as
    static files. `launch_url` is the public URL of the entry HTML.
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
