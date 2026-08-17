"""Qualification tracks — built on LearningPath rows whose
metadata_json contains {"qualification": true}."""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from models import (
    Certificate, CourseStatus, Enrollment, EnrollmentStatus,
    LearningPath, LearningPathStatus,
)

logger = logging.getLogger(__name__)


def _meta(p: LearningPath) -> dict:
    try:
        return json.loads(p.metadata_json or "{}")
    except Exception:
        return {}


def _qual_paths(db: Session, org_id: int) -> list[LearningPath]:
    rows = db.query(LearningPath).filter(
        LearningPath.organization_id == org_id,
        LearningPath.status == LearningPathStatus.PUBLISHED,
    ).all()
    return [p for p in rows if _meta(p).get("qualification")]


def pathway_map(db: Session, user) -> list[dict]:
    """Learner-facing view: each track with per-stage lock/progress state."""
    from services.prerequisite_service import get_unmet_prerequisites
    paths = _qual_paths(db, user.organization_id)
    enrs = {e.course_id: e for e in db.query(Enrollment).filter(
        Enrollment.user_id == user.id).all()}
    out = []
    for p in paths:
        meta = _meta(p)
        stages = []
        for item in p.items:
            c = item.course
            if not c:
                continue
            e = enrs.get(c.id)
            if e and e.status == EnrollmentStatus.COMPLETED:
                state = "completed"
            elif e:
                state = "in_progress"
            elif c.status != CourseStatus.PUBLISHED:
                state = "coming_soon"
            elif get_unmet_prerequisites(db, user.id, c.id):
                state = "locked"
            else:
                state = "available"
            stages.append({
                "course_id": c.id, "title": c.title,
                "order": item.order_index,
                "course_status": c.status.value, "state": state,
                "progress": round(e.progress or 0, 1) if e else 0,
                "is_required": item.is_required,
            })
        cert = db.query(Certificate).filter(
            Certificate.user_id == user.id,
            Certificate.type == "QUALIFICATION",
            Certificate.learning_path_id == p.id,
            Certificate.revoked_at.is_(None),
        ).first()
        out.append({
            "id": p.id, "title": p.title, "description": p.description,
            "designation": meta.get("designation"),
            "nqf_level": meta.get("nqf_level"),
            "total_credits": meta.get("total_credits"),
            "unit_standards": meta.get("unit_standards", []),
            "qualification_earned": cert is not None,
            "certificate_id": cert.id if cert else None,
            "stages": stages,
        })
    return out


def check_and_award_qualifications(db: Session, user) -> list[str]:
    """Issue a QUALIFICATION certificate for every fully-completed track.
    Idempotent. Returns designations awarded this call. Caller commits."""
    completed = {e.course_id for e in db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.status == EnrollmentStatus.COMPLETED).all()}
    awarded: list[str] = []
    for p in _qual_paths(db, user.organization_id):
        required = [i.course_id for i in p.items if i.is_required]
        if not required or not set(required) <= completed:
            continue
        existing = db.query(Certificate).filter(
            Certificate.user_id == user.id,
            Certificate.type == "QUALIFICATION",
            Certificate.learning_path_id == p.id,
        ).first()
        if existing:
            continue
        meta = _meta(p)
        designation = meta.get("designation") or p.title
        db.add(Certificate(user_id=user.id, type="QUALIFICATION",
                           learning_path_id=p.id))
        try:
            from services.gamification_service import GamificationService
            GamificationService(db).notify(
                user.id, "QUALIFICATION_EARNED",
                f"🏆 Qualification earned: {designation}",
                f"You completed the full {p.title} — your qualification "
                "certificate is ready to download.",
                "/certificates")
        except Exception as ex:
            logger.warning("Qualification notify failed: %s", ex)
        awarded.append(designation)
    return awarded


def admin_completions(db: Session, org_id: int) -> list[dict]:
    """Compliance matrix: per track, learner × module states."""
    from models import User, UserRole
    paths = _qual_paths(db, org_id)
    learners = (db.query(User).join(UserRole, UserRole.user_id == User.id)
                .filter(User.organization_id == org_id,
                        UserRole.role == "LEARNER")
                .order_by(User.name, User.email).all())
    learner_ids = [u.id for u in learners]
    enrs: dict[tuple[int, int], Enrollment] = {}
    if learner_ids:
        for e in db.query(Enrollment).filter(
                Enrollment.user_id.in_(learner_ids)).all():
            enrs[(e.user_id, e.course_id)] = e
    qual_certs = set()
    if learner_ids:
        for c in db.query(Certificate).filter(
                Certificate.user_id.in_(learner_ids),
                Certificate.type == "QUALIFICATION",
                Certificate.revoked_at.is_(None)).all():
            qual_certs.add((c.user_id, c.learning_path_id))
    out = []
    for p in paths:
        meta = _meta(p)
        courses = [{"course_id": i.course_id, "title": i.course.title}
                   for i in p.items if i.course]
        rows = []
        for u in learners:
            cells = []
            for c in courses:
                e = enrs.get((u.id, c["course_id"]))
                if e and e.status == EnrollmentStatus.COMPLETED:
                    state = "rpl" if e.via_rpl else "completed"
                elif e:
                    state = "in_progress"
                else:
                    state = "not_started"
                cells.append({"course_id": c["course_id"], "state": state,
                              "progress": round(e.progress or 0, 1) if e else 0})
            rows.append({"user_id": u.id, "name": u.name, "email": u.email,
                         "cells": cells,
                         "qualified": (u.id, p.id) in qual_certs})
        out.append({"id": p.id, "title": p.title,
                    "designation": meta.get("designation"),
                    "nqf_level": meta.get("nqf_level"),
                    "total_credits": meta.get("total_credits"),
                    "courses": courses, "learners": rows})
    return out


def grant_rpl(db: Session, admin, user_id: int, course_id: int) -> dict:
    """Mark a module completed via RPL. No course certificate; counts
    toward prerequisites and qualification awards."""
    from datetime import datetime, timezone
    from fastapi import HTTPException
    from models import Course, User
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == admin.organization_id).first()
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == admin.organization_id).first()
    if not user or not course:
        raise HTTPException(status_code=404, detail="User or course not found")
    e = db.query(Enrollment).filter(
        Enrollment.user_id == user_id,
        Enrollment.course_id == course_id).first()
    if e and e.status == EnrollmentStatus.COMPLETED and not e.via_rpl:
        raise HTTPException(status_code=409,
                            detail="Already completed normally — RPL not needed")
    if not e:
        e = Enrollment(user_id=user_id, course_id=course_id)
        db.add(e)
    e.status = EnrollmentStatus.COMPLETED
    e.progress = 100.0
    e.via_rpl = True
    e.completed_at = datetime.now(timezone.utc)
    db.flush()
    quals = check_and_award_qualifications(db, user)
    try:
        from services.audit_service import record
        record(db, admin, "RPL_GRANTED", target_type="course",
               target_id=str(course_id),
               metadata={"learner_email": user.email,
                         "course_title": course.title})
    except Exception:
        pass
    db.commit()
    return {"ok": True, "qualifications_earned": quals}


def revoke_rpl(db: Session, admin, user_id: int, course_id: int) -> dict:
    from fastapi import HTTPException
    from models import User
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == admin.organization_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    e = db.query(Enrollment).filter(
        Enrollment.user_id == user_id,
        Enrollment.course_id == course_id,
        Enrollment.via_rpl.is_(True)).first()
    if not e:
        raise HTTPException(status_code=404, detail="No RPL grant found")
    db.delete(e)
    db.commit()
    return {"ok": True}
