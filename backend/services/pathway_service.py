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
