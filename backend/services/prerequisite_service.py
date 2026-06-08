"""Prerequisite enforcement — guards `enroll` so learners can't skip ahead."""
from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from models import Course, CoursePrerequisite, Enrollment, EnrollmentStatus


def get_unmet_prerequisites(db: Session, user_id: int,
                            course_id: int) -> List[Tuple[int, str]]:
    """Returns a list of (prereq_course_id, prereq_title) the user has NOT
    completed yet. Empty list = clear to enrol."""
    prereqs = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
    ).all()
    if not prereqs:
        return []
    prereq_ids = [p.prerequisite_course_id for p in prereqs]
    completed = {
        e.course_id for e in db.query(Enrollment).filter(
            Enrollment.user_id == user_id,
            Enrollment.course_id.in_(prereq_ids),
            Enrollment.status == EnrollmentStatus.COMPLETED,
        ).all()
    }
    unmet = [pid for pid in prereq_ids if pid not in completed]
    if not unmet:
        return []
    courses = {
        c.id: c.title for c in db.query(Course).filter(Course.id.in_(unmet)).all()
    }
    return [(pid, courses.get(pid, f"Course #{pid}")) for pid in unmet]
