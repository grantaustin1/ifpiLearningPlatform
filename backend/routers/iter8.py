"""Audit log read API + cohorts list + learner PDF transcript.

Iteration 8 additions:
- GET /api/admin/audit-log — paginated list with filters (admin only, own org)
- GET /api/admin/cohorts — distinct cohort labels in the caller's org
- GET /api/admin/reports/cohort-stats?cohort=X — completion/score stats
- GET /api/certificates/transcript — branded PDF transcript for the calling user
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
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


@router.get("/api/admin/leaderboard.csv")
def leaderboard_csv(cohort: Optional[str] = None,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    q = db.query(User).filter(
        User.organization_id == current.organization_id, User.is_active.is_(True),
    )
    if cohort:
        q = q.filter(User.cohort == cohort)
    rows = q.order_by(User.points.desc().nullslast()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "name", "email", "cohort", "xp", "badges_earned", "certificates"])
    for i, u in enumerate(rows, 1):
        badges = db.query(UserBadge).filter(UserBadge.user_id == u.id).count()
        certs = db.query(Certificate).filter(Certificate.user_id == u.id).count()
        w.writerow([i, u.name or "", u.email, u.cohort or "", u.points or 0, badges, certs])
    name = f"leaderboard{'_' + cohort if cohort else ''}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )


@router.get("/api/admin/audit-digest")
async def audit_digest(
    days: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """LLM-generated plain-English summary of the last N days of admin
    activity in this org. Falls back to a deterministic stats-only summary
    when the LLM call fails so the page always renders something useful."""
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    # Iter 38 — was `.all()` unbounded: at 10× traffic the audit log
    # can hit 100k+ rows/month. Load COUNTS via SQL aggregation (one
    # row per distinct action) and a small sample (300 rows) for the
    # LLM digest. Prevents OOM on large tenants.
    from sqlalchemy import func as _func
    action_counts = (db.query(AuditLog.action, _func.count(AuditLog.id))
                     .filter(AuditLog.organization_id == current.organization_id,
                             AuditLog.created_at >= since)
                     .group_by(AuditLog.action)
                     .all())
    by_action: dict[str, int] = {a: n for a, n in action_counts}
    total_rows = sum(by_action.values())
    # Bounded sample for LLM context — the digest doesn't benefit from
    # more than the most recent few hundred rows anyway.
    rows = (db.query(AuditLog)
            .filter(AuditLog.organization_id == current.organization_id,
                    AuditLog.created_at >= since)
            .order_by(AuditLog.created_at.desc())
            .limit(300).all())
    deterministic = (
        f"In the last {days} days: {total_rows} admin action(s) recorded."
        + ((" "
            + ", ".join(f"{k.replace('_', ' ').title()}: {v}"
                        for k, v in sorted(by_action.items(), key=lambda kv: -kv[1])[:6])
            + ".") if by_action else " No admin activity to summarise.")
    )
    digest = deterministic
    if rows:
        try:
            from core.config import settings
            if settings.emergent_llm_key:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                import uuid as _uuid
                lines = "\n".join(
                    f"- {r.created_at:%Y-%m-%d}  {r.action}  {r.target_type or ''}#{r.target_id or ''}  meta={r.audit_metadata}"
                    for r in rows[:80]
                )
                chat = LlmChat(api_key=settings.emergent_llm_key,
                               session_id=f"digest-{_uuid.uuid4().hex}",
                               system_message="You produce concise, executive-friendly summaries of admin activity. 3-5 sentences, plain English, no jargon, no markdown.").with_model(
                    settings.ai_builder_provider, settings.ai_builder_model)
                resp = await chat.send_message(UserMessage(
                    text=f"Summarise the last {days} days of admin activity for an "
                         f"IFPI Learning academy. Counts: {by_action}\n\nRaw rows:\n{lines}"))
                digest = (resp if isinstance(resp, str) else getattr(resp, "content", str(resp))).strip()
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("ifpi.audit_digest").exception("digest LLM call failed: %s", e)
            digest = deterministic + " (AI summary unavailable — see logs.)"
    return {
        "days": days, "total_actions": len(rows),
        "counts_by_action": by_action,
        "summary": digest,
    }


# ── Learner PDF transcript ───────────────────────────────────────────
@router.get("/api/certificates/transcript.json")
def my_transcript_json(db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    """Iter 50 — JSON payload behind the printable transcript page.
    Same data as the PDF: completed courses (best exam score + date),
    certificates, badges, XP."""
    from models import Exam, LiveSession
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
    attempt_rows = db.query(ExamAttempt, Exam.course_id).join(
        Exam, Exam.id == ExamAttempt.exam_id).filter(
        ExamAttempt.user_id == user.id, ExamAttempt.score.isnot(None),
    ).all()
    best_score: dict[int, float] = {}
    for a, cid in attempt_rows:
        if cid and (cid not in best_score or a.score > best_score[cid]):
            best_score[cid] = a.score
    certs = db.query(Certificate).filter(
        Certificate.user_id == user.id,
    ).order_by(Certificate.issued_at.desc()).all()
    session_titles = {}
    sess_ids = [c.live_session_id for c in certs if c.live_session_id]
    if sess_ids:
        session_titles = {s.id: s.title for s in db.query(LiveSession).filter(
            LiveSession.id.in_(sess_ids)).all()}
    badges = db.query(UserBadge).filter(UserBadge.user_id == user.id).order_by(
        UserBadge.earned_at.asc()).all()
    return {
        "learner": {"name": user.name, "email": user.email,
                    "cohort": user.cohort, "total_xp": user.points or 0},
        "organization": {"name": org.name if org else "IFPI Learning",
                         "primary_color": (org.primary_color if org else None) or "#6366f1",
                         "logo_url": org.logo_url if org else None},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "courses": [{
            "id": e.course_id,
            "title": courses[e.course_id].title,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "best_score": best_score.get(e.course_id),
        } for e in enrolls if e.course_id in courses],
        "certificates": [{
            "id": c.id, "code": c.code, "type": c.type,
            "title": (c.course.title if c.course
                      else session_titles.get(c.live_session_id, "Certificate")),
            "issued_at": c.issued_at.isoformat() if c.issued_at else None,
            "revoked": c.revoked_at is not None,
        } for c in certs],
        "badges": [{
            "badge": b.badge,
            "earned_at": b.earned_at.isoformat() if b.earned_at else None,
        } for b in badges],
    }


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
    # Join exam→course once instead of touching a.exam.course_id N times
    from models import Exam
    attempt_rows = db.query(ExamAttempt, Exam.course_id).join(Exam, Exam.id == ExamAttempt.exam_id).filter(
        ExamAttempt.user_id == user.id, ExamAttempt.score.isnot(None),
    ).order_by(ExamAttempt.completed_at.desc().nullslast()).all()
    best_score_per_course: dict[int, float] = {}
    for a, cid in attempt_rows:
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
