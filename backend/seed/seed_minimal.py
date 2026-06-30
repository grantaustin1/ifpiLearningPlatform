"""Idempotent seed: default IFPI academy + admin + learner + one sample course/exam."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.security import get_password_hash
from models import (
    BadgeTier, Course, CourseSlide, CourseStatus, Enrollment, EnrollmentStatus,
    Exam, ExamQuestion, LifecycleStage, Organization, Person, QuestionType,
    SlideType, User, UserRole,
)

logger = logging.getLogger(__name__)

_DEFAULT_BADGE_TIERS = [
    ("FIRST_ENROLLMENT", "First Step",    "🎯", "Enrolled in your first course",  10, 0),
    ("FIRST_COURSE",     "Graduate",      "🎓", "Completed your first course",    50, 1),
    ("EXAM_PASSER",      "Scholar",       "📚", "Passed your first exam",        100, 2),
    ("PERFECT_SCORE",    "Perfectionist", "💯", "Scored 100% on an exam",        200, 3),
    ("COURSE_MASTER",    "Course Master", "🏆", "Completed 5 courses",           500, 4),
]


def seed(db: Session) -> None:
    # 1. Default academy
    org = db.query(Organization).filter(Organization.slug == "ifpi-main").first()
    if not org:
        org = Organization(
            name="IFPI Main Academy", slug="ifpi-main",
            description="The primary training portal for IFPI members",
            primary_color="#6366f1",
        )
        db.add(org)
        db.flush()
        logger.info("Seeded academy: %s", org.name)

    # 2. Admin user
    admin = db.query(User).filter(User.email == "admin@ifpi.org").first()
    if not admin:
        admin = User(
            email="admin@ifpi.org", name="IFPI Admin",
            password_hash=get_password_hash("admin123"),
            organization_id=org.id, is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role="ADMIN"))
        db.add(UserRole(user_id=admin.id, role="SUPER_ADMIN"))
        db.add(Person(user_id=admin.id, organization_id=org.id,
                      email=admin.email, name=admin.name,
                      lifecycle_stage=LifecycleStage.LEARNER, source="seed"))
        logger.info("Seeded admin: %s / admin123", admin.email)
    else:
        # Ensure SUPER_ADMIN role exists for existing admin (idempotent)
        has_super = db.query(UserRole).filter(
            UserRole.user_id == admin.id, UserRole.role == "SUPER_ADMIN"
        ).first()
        if not has_super:
            db.add(UserRole(user_id=admin.id, role="SUPER_ADMIN"))
            db.flush()
            logger.info("Added SUPER_ADMIN role to existing admin")

    # 3. Learner user
    learner = db.query(User).filter(User.email == "learner@ifpi.org").first()
    if not learner:
        learner = User(
            email="learner@ifpi.org", name="Test Learner",
            password_hash=get_password_hash("learner123"),
            organization_id=org.id, is_active=True,
        )
        db.add(learner)
        db.flush()
        db.add(UserRole(user_id=learner.id, role="LEARNER"))
        db.add(Person(user_id=learner.id, organization_id=org.id,
                      email=learner.email, name=learner.name,
                      lifecycle_stage=LifecycleStage.LEARNER, source="seed"))
        logger.info("Seeded learner: %s / learner123", learner.email)

    # 3b. AGENT008 cohort learner (required for leaderboard cohort-filter tests)
    agent_learner = db.query(User).filter(User.email == "agent008@ifpi.org").first()
    if not agent_learner:
        agent_learner = User(
            email="agent008@ifpi.org", name="Agent008 Learner",
            password_hash=get_password_hash("learner123"),
            organization_id=org.id, is_active=True,
            cohort="AGENT008",
        )
        db.add(agent_learner)
        db.flush()
        db.add(UserRole(user_id=agent_learner.id, role="LEARNER"))
        db.add(Person(user_id=agent_learner.id, organization_id=org.id,
                      email=agent_learner.email, name=agent_learner.name,
                      lifecycle_stage=LifecycleStage.LEARNER, source="seed"))
        logger.info("Seeded AGENT008 cohort learner: %s", agent_learner.email)

    # 4. Sample course
    course = db.query(Course).filter(Course.title == "IFPI Fundamentals").first()
    if not course:
        course = Course(
            organization_id=org.id, title="IFPI Fundamentals",
            description="Introduction to IFPI — mission, structure, and key programs.",
            category="Foundation", status=CourseStatus.PUBLISHED,
            passing_score=70, duration_minutes=45,
            price_cents=0, currency="ZAR", created_by_id=admin.id,
            cover_color="bg-blue-500",
        )
        db.add(course)
        db.flush()
        slides = [
            ("Welcome to IFPI",
             "<h2>Welcome to IFPI Fundamentals</h2><p>This course gives you a comprehensive overview of IFPI — who we are, what we do, and how we support the global recorded music industry.</p>"),
            ("What is IFPI?",
             "<h2>What is IFPI?</h2><p>The International Federation of the Phonographic Industry represents the recording industry worldwide.</p><ul><li>Over 8,000 record labels</li><li>Active in 66 countries</li><li>Founded in 1933</li><li>Headquartered in London</li></ul>"),
            ("Our Mission",
             "<h2>IFPI's Mission</h2><ol><li><strong>Licensing</strong> — ensuring rights are properly licensed</li><li><strong>Anti-piracy</strong> — combating illegal copying</li><li><strong>Government relations</strong> — advocating for fair copyright laws</li></ol>"),
            ("Global Music Report",
             "<h2>Global Music Report</h2><p>Each year IFPI publishes the definitive source of data on the international recorded music market.</p><ul><li>Streaming = 67% of global revenues</li><li>Physical music grew for the third consecutive year</li></ul>"),
            ("Summary & Next Steps",
             "<h2>Congratulations!</h2><p>You've completed the IFPI Fundamentals overview. Take the assessment to earn your certificate.</p>"),
        ]
        for i, (title, content) in enumerate(slides, 1):
            db.add(CourseSlide(
                course_id=course.id, title=title, content=content,
                slide_type=SlideType.TEXT, order_index=i,
            ))
        logger.info("Seeded course: %s", course.title)

    # 4b. Completed enrollment for AGENT008 learner (needed for cohort-stats and
    # cohort celebration tests which require completion_rate >= threshold).
    if not db.query(Enrollment).filter(
        Enrollment.user_id == agent_learner.id,
        Enrollment.course_id == course.id,
    ).first():
        _now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(Enrollment(
            user_id=agent_learner.id, course_id=course.id,
            status=EnrollmentStatus.COMPLETED,
            enrolled_at=_now, completed_at=_now,
        ))
        logger.info("Seeded completed enrollment for AGENT008 learner")

    # 5. Sample exam
    exam = db.query(Exam).filter(Exam.title == "IFPI Fundamentals Assessment").first()
    if not exam:
        exam = Exam(
            organization_id=org.id, title="IFPI Fundamentals Assessment",
            description="Test your knowledge of IFPI's mission and structure.",
            course_id=course.id, time_limit_minutes=15, passing_score=70,
            max_attempts=3, is_published=True, created_by_id=admin.id,
        )
        db.add(exam)
        db.flush()
        qs = [
            ("What does IFPI stand for?", "MULTIPLE_CHOICE",
             ["International Federation of the Phonographic Industry",
              "International Foundation for Performing Industry",
              "International Forum for Publishing Interests",
              "International Fund for Phonographic Innovation"], "0"),
            ("In which year was IFPI founded?", "MULTIPLE_CHOICE",
             ["1920", "1933", "1945", "1960"], "1"),
            ("Where is IFPI headquartered?", "MULTIPLE_CHOICE",
             ["New York", "Paris", "London", "Geneva"], "2"),
            ("Streaming represents the majority of global music revenues.", "TRUE_FALSE",
             ["True", "False"], "true"),
        ]
        for i, (text, qt, opts, correct) in enumerate(qs, 1):
            db.add(ExamQuestion(
                exam_id=exam.id, question_text=text,
                question_type=QuestionType(qt), options=opts,
                correct_answer=correct, points=1, order_index=i,
            ))
        logger.info("Seeded exam: %s", exam.title)

    # 6. Two extra published courses (required for course-reorder test: >= 3 courses)
    for extra_title, extra_desc in [
        ("Copyright Essentials", "Key concepts in music copyright law and licensing."),
        ("Digital Distribution 101", "How recorded music reaches streaming platforms globally."),
    ]:
        if not db.query(Course).filter(Course.title == extra_title).first():
            extra = Course(
                organization_id=org.id, title=extra_title,
                description=extra_desc, category="Foundation",
                status=CourseStatus.PUBLISHED, passing_score=70,
                duration_minutes=30, price_cents=0, currency="ZAR",
                created_by_id=admin.id, cover_color="bg-purple-500",
            )
            db.add(extra)
            db.flush()
            db.add(CourseSlide(
                course_id=extra.id, title="Introduction",
                content=f"<h2>{extra_title}</h2><p>{extra_desc}</p>",
                slide_type=SlideType.TEXT, order_index=1,
            ))
            logger.info("Seeded extra course: %s", extra_title)

    # 7. Default badge tiers for the org (idempotent — skip if already present)
    existing_slugs = {
        r.slug for r in db.query(BadgeTier).filter(BadgeTier.organization_id == org.id).all()
    }
    for slug, label, emoji, description, threshold_xp, order_index in _DEFAULT_BADGE_TIERS:
        if slug not in existing_slugs:
            db.add(BadgeTier(
                organization_id=org.id, slug=slug, label=label,
                emoji=emoji, description=description,
                threshold_xp=threshold_xp, order_index=order_index,
                is_active=True,
            ))
    if existing_slugs != {t[0] for t in _DEFAULT_BADGE_TIERS}:
        logger.info("Seeded default badge tiers for org %s", org.id)

    db.commit()


def run_if_empty() -> None:
    """Idempotent — only seeds if no organization rows exist yet."""
    with SessionLocal() as db:
        if db.query(Organization).count() == 0:
            logger.info("Empty DB detected — running initial seed")
            seed(db)
        else:
            # Still safe to re-run (everything is upsert-by-key)
            seed(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_if_empty()
    print("✅ Seed complete. Login as admin@ifpi.org / admin123 or learner@ifpi.org / learner123")
