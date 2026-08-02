"""Idempotent seed: default IFPI academy + admin + learner + one sample course/exam."""
from __future__ import annotations

import json
import logging
import os
<<<<<<< HEAD
from pathlib import Path
=======
from datetime import datetime, timezone
>>>>>>> origin/main

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.security import get_password_hash
from models import (
<<<<<<< HEAD
    Course, CourseSlide, CourseStatus, Exam, ExamQuestion, LifecycleStage,
    Organization, Person, QuestionType, SlideType, User, UserRole,
=======
    BadgeTier, Course, CourseSlide, CourseStatus, Enrollment, EnrollmentStatus,
    Exam, ExamQuestion, LifecycleStage, Organization, Person, QuestionType,
    SlideType, User, UserRole,
>>>>>>> origin/main
)

logger = logging.getLogger(__name__)

<<<<<<< HEAD
=======
_DEFAULT_BADGE_TIERS = [
    ("FIRST_ENROLLMENT", "First Step",    "🎯", "Enrolled in your first course",  10, 0),
    ("FIRST_COURSE",     "Graduate",      "🎓", "Completed your first course",    50, 1),
    ("EXAM_PASSER",      "Scholar",       "📚", "Passed your first exam",        100, 2),
    ("PERFECT_SCORE",    "Perfectionist", "💯", "Scored 100% on an exam",        200, 3),
    ("COURSE_MASTER",    "Course Master", "🏆", "Completed 5 courses",           500, 4),
]

>>>>>>> origin/main

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
<<<<<<< HEAD
            description="The primary training portal for members of the "
                        "International Fitness Professionals Institute",
=======
            description="The primary training portal for IFPI members",
>>>>>>> origin/main
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
<<<<<<< HEAD
=======
        # Ensure SUPER_ADMIN role exists for existing admin (idempotent)
        has_super = db.query(UserRole).filter(
            UserRole.user_id == admin.id, UserRole.role == "SUPER_ADMIN"
        ).first()
        if not has_super:
            db.add(UserRole(user_id=admin.id, role="SUPER_ADMIN"))
            db.flush()
            logger.info("Added SUPER_ADMIN role to existing admin")
>>>>>>> origin/main
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
<<<<<<< HEAD
=======
        db.add(UserRole(user_id=admin.id, role="SUPER_ADMIN"))
>>>>>>> origin/main
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

<<<<<<< HEAD
=======
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

>>>>>>> origin/main
    # 4. Sample course
    course = db.query(Course).filter(Course.title == "IFPI Fundamentals").first()
    if not course:
        course = Course(
            organization_id=org.id, title="IFPI Fundamentals",
<<<<<<< HEAD
            description="Introduction to IFPI — the International Fitness Professionals Institute: mission, standards, and member programs.",
=======
            description="Introduction to IFPI — mission, structure, and key programs.",
>>>>>>> origin/main
            category="Foundation", status=CourseStatus.PUBLISHED,
            passing_score=70, duration_minutes=45,
            price_cents=0, currency="ZAR", created_by_id=admin.id,
            cover_color="bg-blue-500",
        )
        db.add(course)
        db.flush()
        slides = [
            ("Welcome to IFPI",
<<<<<<< HEAD
             "<h2>Welcome to IFPI Fundamentals</h2><p>This course gives you a comprehensive overview of IFPI — who we are, what we do, and how we support fitness professionals worldwide.</p>"),
            ("What is IFPI?",
             "<h2>What is IFPI?</h2><p>The International Fitness Professionals Institute is the professional body for the fitness industry.</p><ul><li>Personal trainers and group-exercise coaches</li><li>Gyms, boutique studios and wellness centres</li><li>Certification and continuing-education standards</li><li>A global member community</li></ul>"),
            ("Our Mission",
             "<h2>IFPI's Mission</h2><ol><li><strong>Certification standards</strong> — accrediting fitness qualifications you can trust</li><li><strong>Professional development</strong> — continuing education that keeps members current</li><li><strong>Member advocacy</strong> — representing fitness professionals to regulators and insurers</li></ol>"),
            ("The Fitness Industry Landscape",
             "<h2>The Fitness Industry Landscape</h2><p>The health and wellness sector continues to grow and diversify.</p><ul><li>Boutique studios and hybrid gym models are expanding</li><li>Digital and at-home fitness now complement in-person training</li><li>Employers and insurers increasingly require accredited certification</li></ul>"),
=======
             "<h2>Welcome to IFPI Fundamentals</h2><p>This course gives you a comprehensive overview of IFPI — who we are, what we do, and how we support the global recorded music industry.</p>"),
            ("What is IFPI?",
             "<h2>What is IFPI?</h2><p>The International Federation of the Phonographic Industry represents the recording industry worldwide.</p><ul><li>Over 8,000 record labels</li><li>Active in 66 countries</li><li>Founded in 1933</li><li>Headquartered in London</li></ul>"),
            ("Our Mission",
             "<h2>IFPI's Mission</h2><ol><li><strong>Licensing</strong> — ensuring rights are properly licensed</li><li><strong>Anti-piracy</strong> — combating illegal copying</li><li><strong>Government relations</strong> — advocating for fair copyright laws</li></ol>"),
            ("Global Music Report",
             "<h2>Global Music Report</h2><p>Each year IFPI publishes the definitive source of data on the international recorded music market.</p><ul><li>Streaming = 67% of global revenues</li><li>Physical music grew for the third consecutive year</li></ul>"),
>>>>>>> origin/main
            ("Summary & Next Steps",
             "<h2>Congratulations!</h2><p>You've completed the IFPI Fundamentals overview. Take the assessment to earn your certificate.</p>"),
        ]
        for i, (title, content) in enumerate(slides, 1):
            db.add(CourseSlide(
                course_id=course.id, title=title, content=content,
                slide_type=SlideType.TEXT, order_index=i,
            ))
        logger.info("Seeded course: %s", course.title)

<<<<<<< HEAD
=======
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

>>>>>>> origin/main
    # 5. Sample exam
    exam = db.query(Exam).filter(Exam.title == "IFPI Fundamentals Assessment").first()
    if not exam:
        exam = Exam(
            organization_id=org.id, title="IFPI Fundamentals Assessment",
<<<<<<< HEAD
            description="Test your knowledge of IFPI's mission and the fitness industry.",
=======
            description="Test your knowledge of IFPI's mission and structure.",
>>>>>>> origin/main
            course_id=course.id, time_limit_minutes=15, passing_score=70,
            max_attempts=3, is_published=True, created_by_id=admin.id,
        )
        db.add(exam)
        db.flush()
        qs = [
            ("What does IFPI stand for?", "MULTIPLE_CHOICE",
<<<<<<< HEAD
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
=======
             ["International Federation of the Phonographic Industry",
              "International Foundation for Performing Industry",
              "International Forum for Publishing Interests",
              "International Fund for Phonographic Innovation"], "0"),
            ("In which year was IFPI founded?", "MULTIPLE_CHOICE",
             ["1920", "1933", "1945", "1960"], "1"),
            ("Where is IFPI headquartered?", "MULTIPLE_CHOICE",
             ["New York", "Paris", "London", "Geneva"], "2"),
            ("Streaming represents the majority of global music revenues.", "TRUE_FALSE",
>>>>>>> origin/main
             ["True", "False"], "true"),
        ]
        for i, (text, qt, opts, correct) in enumerate(qs, 1):
            db.add(ExamQuestion(
                exam_id=exam.id, question_text=text,
                question_type=QuestionType(qt), options=opts,
                correct_answer=correct, points=1, order_index=i,
            ))
        logger.info("Seeded exam: %s", exam.title)

<<<<<<< HEAD
    # 6. Fitness demo catalog — the three flagship demo courses (slides +
    #    exams + cover photos) so a fresh deployment starts with a stocked
    #    marketplace. Idempotent by course title; cover files ship with the
    #    repo under uploads/covers/.
    try:
        from scripts.seed_fitness_courses import seed_courses
        created = seed_courses(db, org, admin)
        if created:
            logger.info("Seeded %d fitness demo courses", created)
        _covers = {
            "IFPI Fundamentals": "covers/ifpi_fundamentals.jpg",
            "Foundations of Exercise Science": "covers/exercise_science.jpg",
            "Client Onboarding & Consultation Skills": "covers/client_onboarding.jpg",
            "Gym Health & Safety Essentials": "covers/health_safety.jpg",
        }
        uploads_root = Path(__file__).resolve().parents[1] / "uploads"
        for title, key in _covers.items():
            row = db.query(Course).filter(
                Course.title == title, Course.organization_id == org.id,
            ).first()
            if row and not row.cover_image and (uploads_root / key).exists():
                row.cover_image = f"/api/uploads/files/{key}"
        featured = db.query(Course).filter(
            Course.title == "Client Onboarding & Consultation Skills",
            Course.organization_id == org.id,
        ).first()
        if featured:
            featured.is_featured = True
        if not org.marketplace_opt_in:
            org.marketplace_opt_in = True
            logger.info("Enabled marketplace opt-in for %s", org.slug)
    except Exception:
        logger.exception("Fitness demo course seed failed — continuing startup")
=======
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
>>>>>>> origin/main

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
