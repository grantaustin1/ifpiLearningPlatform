"""Idempotent seed: default IFPI academy + admin + learner + one sample course/exam."""
from __future__ import annotations

import json
import logging
import os

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.security import get_password_hash
from models import (
    Course, CourseSlide, CourseStatus, Exam, ExamQuestion, LifecycleStage,
    Organization, Person, QuestionType, SlideType, User, UserRole,
)

logger = logging.getLogger(__name__)


def _seed_admin_password() -> str:
    """Iter 33 — Never commit a literal admin password. Prefer the
    SEED_ADMIN_PASSWORD env var; hard-fail in prod, warn in dev."""
    val = (os.environ.get("SEED_ADMIN_PASSWORD") or "").strip()
    if val:
        return val
    if os.environ.get("ENVIRONMENT", "").lower() == "production":
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD is unset in production. Refusing to seed "
            "with a well-known default. Set the env var and redeploy."
        )
    logger.warning(
        "SEED_ADMIN_PASSWORD not set — falling back to 'admin123' for dev "
        "seed. UNSAFE in production; deploy_precheck.py will block this."
    )
    return "admin123"


def seed(db: Session) -> None:
    # 1. Default academy
    org = db.query(Organization).filter(Organization.slug == "ifpi-main").first()
    if not org:
        org = Organization(
            name="IFPI Main Academy", slug="ifpi-main",
            description="The primary training portal for members of the "
                        "International Fitness Professionals Institute",
            primary_color="#6366f1",
        )
        db.add(org)
        db.flush()
        logger.info("Seeded academy: %s", org.name)

    # 2. Admin user
    # 2. Admin user — idempotent by email. If a row with this email
    #    already exists (whether the operator rotated the password
    #    already or not), we DO NOT touch it. This is critical: every
    #    subsequent redeploy must leave rotated credentials alone.
    admin = db.query(User).filter(User.email == "admin@ifpi.org").first()
    if admin is not None:
        logger.info("Seed: admin@ifpi.org already exists (id=%s) — "
                    "leaving password untouched.", admin.id)
    else:
        seed_pw = _seed_admin_password()
        admin = User(
            email="admin@ifpi.org", name="IFPI Admin",
            password_hash=get_password_hash(seed_pw),
            organization_id=org.id, is_active=True,
            # Iter 32 — force password rotation on first login so
            # nobody ships prod with the seeded password still active.
            must_change_password=True,
        )
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role="ADMIN"))
        db.add(Person(user_id=admin.id, organization_id=org.id,
                      email=admin.email, name=admin.name,
                      lifecycle_stage=LifecycleStage.LEARNER, source="seed"))
        # NEVER log the actual password (it may be a real prod secret).
        # Log only the fact and length so the operator can verify from
        # deploy env vs stdout without exposing the value.
        logger.info("Seeded admin: %s (password from %s, %d chars, "
                    "must_change_password=True)",
                    admin.email,
                    "SEED_ADMIN_PASSWORD env" if os.environ.get("SEED_ADMIN_PASSWORD")
                    else "dev fallback",
                    len(seed_pw))

    # 3. Learner user — same idempotency contract as the admin row.
    learner = db.query(User).filter(User.email == "learner@ifpi.org").first()
    if learner is not None:
        logger.info("Seed: learner@ifpi.org already exists (id=%s) — "
                    "leaving password untouched.", learner.id)
    else:
        # Learner is a demo account, only seeded in non-prod. In prod
        # we don't seed a test learner at all — real learners
        # self-register.
        if os.environ.get("ENVIRONMENT", "").lower() == "production":
            logger.info("Seed: skipping learner@ifpi.org creation in prod.")
        else:
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
            logger.info("Seeded learner: %s (dev-only)", learner.email)

    # 4. Sample course
    course = db.query(Course).filter(Course.title == "IFPI Fundamentals").first()
    if not course:
        course = Course(
            organization_id=org.id, title="IFPI Fundamentals",
            description="Introduction to IFPI — the International Fitness Professionals Institute: mission, standards, and member programs.",
            category="Foundation", status=CourseStatus.PUBLISHED,
            passing_score=70, duration_minutes=45,
            price_cents=0, currency="ZAR", created_by_id=admin.id,
            cover_color="bg-blue-500",
        )
        db.add(course)
        db.flush()
        slides = [
            ("Welcome to IFPI",
             "<h2>Welcome to IFPI Fundamentals</h2><p>This course gives you a comprehensive overview of IFPI — who we are, what we do, and how we support fitness professionals worldwide.</p>"),
            ("What is IFPI?",
             "<h2>What is IFPI?</h2><p>The International Fitness Professionals Institute is the professional body for the fitness industry.</p><ul><li>Personal trainers and group-exercise coaches</li><li>Gyms, boutique studios and wellness centres</li><li>Certification and continuing-education standards</li><li>A global member community</li></ul>"),
            ("Our Mission",
             "<h2>IFPI's Mission</h2><ol><li><strong>Certification standards</strong> — accrediting fitness qualifications you can trust</li><li><strong>Professional development</strong> — continuing education that keeps members current</li><li><strong>Member advocacy</strong> — representing fitness professionals to regulators and insurers</li></ol>"),
            ("The Fitness Industry Landscape",
             "<h2>The Fitness Industry Landscape</h2><p>The health and wellness sector continues to grow and diversify.</p><ul><li>Boutique studios and hybrid gym models are expanding</li><li>Digital and at-home fitness now complement in-person training</li><li>Employers and insurers increasingly require accredited certification</li></ul>"),
            ("Summary & Next Steps",
             "<h2>Congratulations!</h2><p>You've completed the IFPI Fundamentals overview. Take the assessment to earn your certificate.</p>"),
        ]
        for i, (title, content) in enumerate(slides, 1):
            db.add(CourseSlide(
                course_id=course.id, title=title, content=content,
                slide_type=SlideType.TEXT, order_index=i,
            ))
        logger.info("Seeded course: %s", course.title)

    # 5. Sample exam
    exam = db.query(Exam).filter(Exam.title == "IFPI Fundamentals Assessment").first()
    if not exam:
        exam = Exam(
            organization_id=org.id, title="IFPI Fundamentals Assessment",
            description="Test your knowledge of IFPI's mission and the fitness industry.",
            course_id=course.id, time_limit_minutes=15, passing_score=70,
            max_attempts=3, is_published=True, created_by_id=admin.id,
        )
        db.add(exam)
        db.flush()
        qs = [
            ("What does IFPI stand for?", "MULTIPLE_CHOICE",
             ["International Fitness Professionals Institute",
              "International Federation of Personal Instructors",
              "Institute for Fitness Program Innovation",
              "International Forum for Physical Instruction"], "0"),
            ("Which of the following is part of IFPI's mission?", "MULTIPLE_CHOICE",
             ["Operating gym franchises directly",
              "Accrediting fitness qualifications and certification standards",
              "Manufacturing exercise equipment",
              "Selling health insurance"], "1"),
            ("Who does IFPI primarily serve?", "MULTIPLE_CHOICE",
             ["Professional athletes only", "Physiotherapy clinics",
              "Fitness professionals, gyms and studios", "Sports broadcasters"], "2"),
            ("Continuing professional development helps fitness professionals keep their certifications current.", "TRUE_FALSE",
             ["True", "False"], "true"),
        ]
        for i, (text, qt, opts, correct) in enumerate(qs, 1):
            db.add(ExamQuestion(
                exam_id=exam.id, question_text=text,
                question_type=QuestionType(qt), options=opts,
                correct_answer=correct, points=1, order_index=i,
            ))
        logger.info("Seeded exam: %s", exam.title)

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
