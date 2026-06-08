"""Audit log read API + cohorts list + learner PDF transcript.

Iteration 8 additions:
- GET /api/admin/audit-log — paginated list with filters (admin only, own org)
- GET /api/admin/cohorts — distinct cohort labels in the caller's org
- GET /api/admin/reports/cohort-stats?cohort=X — completion/score stats
- GET /api/certificates/transcript — branded PDF transcript for the calling user
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import (
    AuditLog, Certificate, Course, Enrollment, EnrollmentStatus,
    ExamAttempt, Organization, User, UserBadge,
)

router = APIRouter(tags=["Audit & Reports"])

# ── Audit log ────────────────────────────────────────────────────────
@router.get("/api/admin/audit-log")
def list_audit(
    actor: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    q = db.query(AuditLog).filter(AuditLog.organization_id == current.organization_id)
    if actor is not None:
        q = q.filter(AuditLog.actor_user_id == actor)
    if action:
        q = q.filter(AuditLog.action == action.upper())
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    actor_ids = {r.actor_user_id for r in rows if r.actor_user_id}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()}
    return {
        "total": total,
        "items": [{
            "id": r.id, "action": r.action,
            "target_type": r.target_type, "target_id": r.target_id,
            "metadata": r.audit_metadata or {},
            "ip_address": r.ip_address,
            "actor": {"id": r.actor_user_id, "email": users[r.actor_user_id].email,
                      "name": users[r.actor_user_id].name} if r.actor_user_id in users else None,
            "created_at": r.created_at,
        } for r in rows],
    }


# ── Cohorts ──────────────────────────────────────────────────────────
@router.get("/api/admin/cohorts")
def list_cohorts(db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Distinct cohort labels with learner counts."""
    rows = db.query(User.cohort, func.count(User.id)).filter(
        User.organization_id == current.organization_id,
        User.cohort.isnot(None),
        User.cohort != "",
    ).group_by(User.cohort).all()
    return [{"cohort": r[0], "learner_count": r[1]} for r in rows]


@router.get("/api/admin/reports/cohort-stats")
def cohort_stats(
    cohort: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Completion / exam-score / time-to-graduation for a cohort, or for
    all learners if cohort is omitted."""
    base = db.query(User).filter(User.organization_id == current.organization_id)
    if cohort:
        base = base.filter(User.cohort == cohort)
    user_ids = [u.id for u in base.all()]
    if not user_ids:
        return {"cohort": cohort, "learners": 0, "enrollments": 0, "completions": 0,
                "completion_rate": 0, "avg_exam_score": 0, "certificates_issued": 0,
                "badges_earned": 0}
    enrollments = db.query(Enrollment).filter(Enrollment.user_id.in_(user_ids))
    total_enr = enrollments.count()
    completed = enrollments.filter(Enrollment.status == EnrollmentStatus.COMPLETED).count()
    avg_score = db.query(func.avg(ExamAttempt.score)).filter(
        ExamAttempt.user_id.in_(user_ids),
        ExamAttempt.score.isnot(None),
    ).scalar() or 0
    certs = db.query(Certificate).filter(Certificate.user_id.in_(user_ids)).count()
    badges = db.query(UserBadge).filter(UserBadge.user_id.in_(user_ids)).count()
    return {
        "cohort": cohort, "learners": len(user_ids),
        "enrollments": total_enr, "completions": completed,
        "completion_rate": round((completed / total_enr) * 100, 1) if total_enr else 0,
        "avg_exam_score": round(float(avg_score), 1),
        "certificates_issued": certs, "badges_earned": badges,
    }


# ── Learner PDF transcript ───────────────────────────────────────────
@router.get("/api/certificates/transcript")
def my_transcript(db: Session = Depends(get_db),
                  current: CurrentUser = Depends(get_current_user)):
    """Generate a branded PDF transcript for the calling user. Lists every
    completed course, exam score, badge earned, total XP, and cohort.
    Useful for job applications and CV submissions."""
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    enrolls = db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.status == EnrollmentStatus.COMPLETED,
    ).all()
    courses = {c.id: c for c in db.query(Course).filter(
        Course.id.in_([e.course_id for e in enrolls])).all()}
    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == user.id, ExamAttempt.score.isnot(None),
    ).order_by(ExamAttempt.completed_at.desc().nullslast()).all()
    best_score_per_course: dict[int, float] = {}
    for a in attempts:
        cid = None
        try:
            cid = a.exam.course_id if a.exam else None
        except Exception:
            cid = None
        if cid and (cid not in best_score_per_course or a.score > best_score_per_course[cid]):
            best_score_per_course[cid] = a.score
    badges = db.query(UserBadge).filter(UserBadge.user_id == user.id).order_by(UserBadge.earned_at.asc()).all()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    accent = HexColor(org.primary_color or "#6366f1") if org else HexColor("#6366f1")
    # Header band
    c.setFillColor(accent); c.rect(0, H - 3.2*cm, W, 3.2*cm, fill=1, stroke=0)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 22)
    c.drawString(2*cm, H - 2.1*cm, "Learner Transcript")
    c.setFont("Helvetica", 11)
    c.drawString(2*cm, H - 2.8*cm, (org.name if org else "IFPI Learning"))

    # Learner block
    y = H - 4.5*cm
    c.setFillColor(HexColor("#0f172a")); c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, y, user.name or user.email)
    c.setFont("Helvetica", 9); c.setFillColor(HexColor("#64748b"))
    y -= 0.5*cm; c.drawString(2*cm, y, f"Email: {user.email}")
    if user.cohort:
        y -= 0.4*cm; c.drawString(2*cm, y, f"Cohort: {user.cohort}")
    y -= 0.4*cm; c.drawString(2*cm, y, f"Total XP: {user.points or 0}")
    y -= 0.4*cm; c.drawString(2*cm, y, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

    # Completed courses
    y -= 0.9*cm
    c.setFillColor(accent); c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Completed courses")
    y -= 0.2*cm; c.setStrokeColor(accent); c.line(2*cm, y, W - 2*cm, y); y -= 0.4*cm
    c.setFont("Helvetica", 10); c.setFillColor(HexColor("#0f172a"))
    if not enrolls:
        c.setFillColor(HexColor("#94a3b8")); c.drawString(2*cm, y, "— no courses completed yet —"); y -= 0.5*cm
    for e in enrolls:
        course = courses.get(e.course_id)
        if not course:
            continue
        date = e.completed_at.strftime("%Y-%m-%d") if e.completed_at else "—"
        score = best_score_per_course.get(course.id)
        score_str = f"{score:.0f}%" if score is not None else "n/a"
        c.setFillColor(HexColor("#0f172a")); c.drawString(2*cm, y, f"• {course.title}")
        c.setFillColor(HexColor("#64748b")); c.drawRightString(W - 2*cm, y, f"{date}   Score: {score_str}")
        y -= 0.5*cm
        if y < 3*cm:
            c.showPage(); y = H - 2*cm

    # Badges
    if badges:
        y -= 0.4*cm
        c.setFillColor(accent); c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y, "Badges earned")
        y -= 0.2*cm; c.line(2*cm, y, W - 2*cm, y); y -= 0.4*cm
        c.setFont("Helvetica", 10); c.setFillColor(HexColor("#0f172a"))
        for b in badges:
            date = b.earned_at.strftime("%Y-%m-%d") if b.earned_at else ""
            c.drawString(2*cm, y, f"• {b.badge}")
            c.setFillColor(HexColor("#64748b")); c.drawRightString(W - 2*cm, y, date)
            c.setFillColor(HexColor("#0f172a"))
            y -= 0.5*cm
            if y < 3*cm:
                c.showPage(); y = H - 2*cm

    # Footer
    c.setFont("Helvetica-Oblique", 7); c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(W/2, 1.2*cm,
        f"Issued by {org.name if org else 'IFPI Learning'} · This document does not constitute a certificate of credit unless accompanied by individual course certificates.")
    c.showPage(); c.save()
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=transcript_{user.id}.pdf"},
    )
