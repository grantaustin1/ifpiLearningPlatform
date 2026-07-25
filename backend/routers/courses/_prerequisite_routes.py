from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import Course

from . import router


@router.get("/{course_id}/prerequisites")
def list_prerequisites(course_id: int, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    from models import CoursePrerequisite
    rows = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
    ).all()
    out = []
    for r in rows:
        pc = db.query(Course).filter(Course.id == r.prerequisite_course_id).first()
        if pc:
            out.append({"id": r.id, "course_id": pc.id, "title": pc.title, "status": pc.status.value})
    return out


@router.post("/{course_id}/prerequisites/{prereq_course_id}")
def add_prerequisite(course_id: int, prereq_course_id: int, db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from models import CoursePrerequisite
    if course_id == prereq_course_id:
        raise HTTPException(status_code=400, detail="Course can't be its own prerequisite")
    # Both courses must belong to this org
    for cid in (course_id, prereq_course_id):
        if not db.query(Course).filter(
            Course.id == cid, Course.organization_id == current.organization_id,
        ).first():
            raise HTTPException(status_code=404, detail=f"Course #{cid} not found")
    existing = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
        CoursePrerequisite.prerequisite_course_id == prereq_course_id,
    ).first()
    if existing:
        return {"ok": True, "already": True}
    db.add(CoursePrerequisite(course_id=course_id, prerequisite_course_id=prereq_course_id))
    db.commit()
    return {"ok": True, "already": False}


@router.delete("/{course_id}/prerequisites/{prereq_course_id}")
def remove_prerequisite(course_id: int, prereq_course_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    from models import CoursePrerequisite
    row = db.query(CoursePrerequisite).filter(
        CoursePrerequisite.course_id == course_id,
        CoursePrerequisite.prerequisite_course_id == prereq_course_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Prerequisite not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
