"""One-off content fix: rebrand the seeded sample course/exam from the
music-industry copy to fitness-industry copy (IFPI = International Fitness
Professionals Institute). Updates rows IN PLACE (ids preserved, learner
progress untouched).

Run:  cd /app/backend && python scripts/rebrand_fitness_content.py
      DATABASE_URL=sqlite:////app/backend/snapshots/pre_uat_ifpi_lms.db \
        python scripts/rebrand_fitness_content.py   # also fix the UAT snapshot
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal
from models import Course, CourseSlide, Exam, ExamQuestion

SLIDES = [
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

QUESTIONS = [
    ("What does IFPI stand for?",
     ["International Fitness Professionals Institute",
      "International Federation of Personal Instructors",
      "Institute for Fitness Program Innovation",
      "International Forum for Physical Instruction"], "0"),
    ("Which of the following is part of IFPI's mission?",
     ["Operating gym franchises directly",
      "Accrediting fitness qualifications and certification standards",
      "Manufacturing exercise equipment",
      "Selling health insurance"], "1"),
    ("Who does IFPI primarily serve?",
     ["Professional athletes only", "Physiotherapy clinics",
      "Fitness professionals, gyms and studios", "Sports broadcasters"], "2"),
    ("Continuing professional development helps fitness professionals keep their certifications current.",
     ["True", "False"], "true"),
]


def main() -> None:
    with SessionLocal() as db:
        changed = 0
        for course in db.query(Course).filter(Course.title == "IFPI Fundamentals").all():
            course.description = ("Introduction to IFPI — the International Fitness "
                                  "Professionals Institute: mission, standards, and member programs.")
            slides = (db.query(CourseSlide)
                      .filter(CourseSlide.course_id == course.id)
                      .order_by(CourseSlide.order_index).all())
            for slide, (title, content) in zip(slides, SLIDES):
                slide.title, slide.content = title, content
                slide.narration_url = None  # stale music-topic narration, if any
            changed += 1
            print(f"updated course id={course.id} (org={course.organization_id}), {len(slides)} slides")

        for exam in db.query(Exam).filter(Exam.title == "IFPI Fundamentals Assessment").all():
            exam.description = "Test your knowledge of IFPI's mission and the fitness industry."
            questions = (db.query(ExamQuestion)
                         .filter(ExamQuestion.exam_id == exam.id)
                         .order_by(ExamQuestion.order_index).all())
            for q, (text, opts, correct) in zip(questions, QUESTIONS):
                q.question_text, q.options, q.correct_answer = text, opts, correct
            changed += 1
            print(f"updated exam id={exam.id}, {len(questions)} questions")

        db.commit()
        print(f"done — {changed} objects rebranded" if changed else "nothing to update")


if __name__ == "__main__":
    main()
