"""Exam routes: CRUD + question management + take + attempt submission."""
from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel as _BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, can_manage_content, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import INSTRUCTOR_ROLES
from models import Course, CourseSlide, Exam, ExamAttempt, ExamQuestion, QuestionType, User
from schemas import (
    AttemptResult, AttemptSubmit, ExamCreate, ExamDetail, ExamSummary,
    ExamUpdate, QuestionIn, QuestionOut,
)
from services.exam_service import ExamService
from services import ai_quiz_service

router = APIRouter(prefix="/api/exams", tags=["Exams"])


def _summary(e: Exam) -> ExamSummary:
    return ExamSummary(
        id=e.id, title=e.title, description=e.description, course_id=e.course_id,
        time_limit_minutes=e.time_limit_minutes, passing_score=e.passing_score,
        max_attempts=e.max_attempts, is_published=e.is_published,
        question_count=len(e.questions), attempt_count=len(e.attempts),
        created_at=e.created_at,
    )


def _detail(e: Exam, user_attempt_count: int = 0) -> ExamDetail:
    return ExamDetail(
        id=e.id, title=e.title, description=e.description, course_id=e.course_id,
        time_limit_minutes=e.time_limit_minutes, passing_score=e.passing_score,
        max_attempts=e.max_attempts, is_published=e.is_published,
        question_count=len(e.questions), attempt_count=len(e.attempts),
        created_at=e.created_at, user_attempt_count=user_attempt_count,
        questions=[QuestionOut(
            id=q.id, question_text=q.question_text,
            question_type=q.question_type.value, options=q.options,
            correct_answer=q.correct_answer, explanation=q.explanation,
            points=q.points, order_index=q.order_index,
        ) for q in e.questions],
    )


def _can_manage(user: CurrentUser) -> bool:
    return can_manage_content(user)


@router.get("", response_model=List[ExamSummary])
def list_exams(db: Session = Depends(get_db),
               current: CurrentUser = Depends(get_current_user)):
    q = db.query(Exam).filter(Exam.organization_id == current.organization_id)
    if not _can_manage(current):
        q = q.filter(Exam.is_published.is_(True))
    return [_summary(e) for e in q.order_by(Exam.created_at.desc()).all()]


@router.post("", response_model=ExamSummary)
def create_exam(body: ExamCreate, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    e = Exam(
        organization_id=current.organization_id, title=body.title,
        description=body.description, course_id=body.course_id,
        time_limit_minutes=body.time_limit_minutes,
        passing_score=body.passing_score, max_attempts=body.max_attempts,
        randomize=body.randomize, is_published=body.is_published,
        created_by_id=current.id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _summary(e)


@router.get("/{exam_id}", response_model=ExamDetail)
def get_exam(exam_id: int, db: Session = Depends(get_db),
             current: CurrentUser = Depends(get_current_user)):
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    if not e.is_published and not _can_manage(current):
        raise HTTPException(status_code=404, detail="Exam not found")
    user_attempts = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == current.id,
    ).count()
    detail = _detail(e, user_attempt_count=user_attempts)
    # Strip answers from the response unless the caller is an admin
    if not _can_manage(current):
        for q in detail.questions:
            q.correct_answer = ""
            q.explanation = ""
    return detail


@router.patch("/{exam_id}", response_model=ExamSummary)
def update_exam(exam_id: int, body: ExamUpdate, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return _summary(e)


@router.delete("/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.put("/{exam_id}/questions", response_model=List[QuestionOut])
def replace_questions(exam_id: int, body: List[QuestionIn],
                      mode: Literal["replace", "append"] = "replace",
                      db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """mode='replace' (default) wipes & sets. mode='append' adds to existing."""
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    if mode == "replace":
        db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete()
        start_idx = 0
    else:
        start_idx = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).count()
    for i, q in enumerate(body):
        qt = q.question_type if q.question_type in QuestionType.__members__ else "MULTIPLE_CHOICE"
        db.add(ExamQuestion(
            exam_id=exam_id, question_text=q.question_text,
            question_type=QuestionType(qt), options=q.options,
            correct_answer=q.correct_answer, explanation=q.explanation,
            points=q.points, order_index=q.order_index or (start_idx + i + 1),
        ))
    db.commit()
    db.refresh(e)
    return [QuestionOut(
        id=q.id, question_text=q.question_text,
        question_type=q.question_type.value, options=q.options,
        correct_answer=q.correct_answer, explanation=q.explanation,
        points=q.points, order_index=q.order_index,
    ) for q in e.questions]


@router.post("/{exam_id}/attempts", response_model=AttemptResult)
def submit_attempt(exam_id: int, body: AttemptSubmit, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)):
    result = ExamService(db).submit_attempt(
        exam_id=exam_id, user_id=current.id,
        organization_id=current.organization_id, answers=body.answers,
    )
    return AttemptResult(**result)


# ── Iter 50 — Admin attempt management ───────────────────────────────
@router.get("/{exam_id}/attempts")
def list_exam_attempts(exam_id: int, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Per-learner attempt summary for an exam (admin/instructor)."""
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    rows = (db.query(ExamAttempt, User)
            .join(User, User.id == ExamAttempt.user_id)
            .filter(ExamAttempt.exam_id == exam_id)
            .order_by(ExamAttempt.completed_at.desc().nullslast())
            .all())
    per_user: dict[int, dict] = {}
    for a, u in rows:
        entry = per_user.setdefault(u.id, {
            "user_id": u.id, "name": u.name, "email": u.email,
            "attempts_used": 0, "best_score": None, "passed": False,
            "last_attempt_at": None,
        })
        entry["attempts_used"] += 1
        if a.score is not None and (entry["best_score"] is None or a.score > entry["best_score"]):
            entry["best_score"] = a.score
        entry["passed"] = entry["passed"] or bool(a.passed)
        ts = a.completed_at or a.started_at
        if ts and (entry["last_attempt_at"] is None or ts.isoformat() > entry["last_attempt_at"]):
            entry["last_attempt_at"] = ts.isoformat()
    return {"exam_id": e.id, "max_attempts": e.max_attempts,
            "learners": list(per_user.values())}


class ResetAttemptsBody(_BaseModel):
    user_id: int


@router.post("/{exam_id}/attempts/reset")
def reset_exam_attempts(exam_id: int, body: ResetAttemptsBody, request: Request,
                        db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Wipe a learner's attempts for one exam so they can retake it."""
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    target = db.query(User).filter(
        User.id == body.user_id,
        User.organization_id == current.organization_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Learner not found")
    n = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == target.id,
    ).delete(synchronize_session=False)
    from services import audit_service
    audit_service.record(db, current, "EXAM_ATTEMPTS_RESET",
                         target_type="exam", target_id=exam_id,
                         metadata={"user_id": target.id, "deleted": n},
                         request=request)
    # Iter 51 — Tell the learner they can retake (email + in-app bell).
    try:
        from services.gamification_service import GamificationService
        from services.mail_service import MailService
        retake_path = f"/take/{e.id}"
        GamificationService(db).notify(
            target.id, "EXAM_ATTEMPTS_RESET",
            "Your exam attempts were reset",
            f'You can retake "{e.title}" — your previous attempts were cleared by an administrator.',
            link=retake_path,
        )
        first_name = (target.name or "there").split()[0]
        MailService(db).send_email(
            to_email=target.email, to_name=target.name,
            subject=f"You can retake: {e.title}",
            body_html=(
                f"<div style='font-family:system-ui,sans-serif;max-width:520px'>"
                f"<h2 style='color:#4f46e5;margin:0 0 12px'>Good news, {first_name}!</h2>"
                f"<p>An administrator reset your attempts for "
                f"<strong>{e.title}</strong>, so you have a fresh set of "
                f"{e.max_attempts} attempt{'s' if e.max_attempts != 1 else ''} to pass it.</p>"
                f"<p style='margin:20px 0'><a href='{retake_path}' "
                f"style='background:#4f46e5;color:#fff;padding:10px 20px;"
                f"border-radius:8px;text-decoration:none;font-weight:600'>Retake the exam</a></p>"
                f"<p style='color:#64748b;font-size:13px'>Pass mark: {e.passing_score}%. Good luck!</p>"
                f"</div>"
            ),
            body_text=(f"An administrator reset your attempts for '{e.title}'. "
                       f"You can retake it at {retake_path} (pass mark {e.passing_score}%)."),
            template="exam_attempts_reset",
            organization_id=current.organization_id, user_id=target.id,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Reset notification queue failed", exc_info=True)
    db.commit()
    return {"deleted": n, "user_id": target.id}


# ── Iter 52 — In-place question edit (preserves id + attempt history) ─
class QuestionPatch(_BaseModel):
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    points: Optional[int] = None


@router.patch("/{exam_id}/questions/{question_id}", response_model=QuestionOut)
def update_question(exam_id: int, question_id: int, body: QuestionPatch,
                    request: Request, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Edit one question in place — unlike PUT /questions (replace), this
    keeps the question id so past attempt answers and insights stay linked."""
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    q = db.query(ExamQuestion).filter(
        ExamQuestion.id == question_id, ExamQuestion.exam_id == exam_id,
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(q, k, v)
    # Iter 53 — editing the question re-arms its miss-rate alert
    q.miss_alerted_at = None
    from services import audit_service
    audit_service.record(db, current, "EXAM_QUESTION_EDITED",
                         target_type="exam", target_id=exam_id,
                         metadata={"question_id": question_id,
                                   "fields": sorted(changes.keys())},
                         request=request)
    db.commit()
    db.refresh(q)
    return QuestionOut(
        id=q.id, question_text=q.question_text,
        question_type=q.question_type.value, options=q.options,
        correct_answer=q.correct_answer, explanation=q.explanation,
        points=q.points, order_index=q.order_index,
    )


# ── Iter 51 — Question insights (miss-rate analytics) ────────────────
@router.get("/{exam_id}/question-insights")
def exam_question_insights(exam_id: int, db: Session = Depends(get_db),
                           current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Per-question correct/miss rates across all attempts, so admins can
    spot the questions (and course content) learners struggle with most."""
    from services.exam_service import grade_question
    e = db.query(Exam).filter(
        Exam.id == exam_id, Exam.organization_id == current.organization_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Exam not found")
    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id, ExamAttempt.answers.isnot(None),
    ).all()
    questions = sorted(e.questions, key=lambda q: q.order_index)
    out = []
    for q in questions:
        answered = correct = 0
        counts: dict[str, int] = {}
        for a in attempts:
            ans = (a.answers or {}).get(str(q.id))
            if ans is None or ans == "":
                continue
            answered += 1
            key = str(ans).strip()
            counts[key] = counts.get(key, 0) + 1
            if grade_question(q, ans):
                correct += 1
        missed = answered - correct
        # Iter 53 — distractor stats: label each picked answer and flag
        # the most-picked wrong one so weak distractors stand out.
        qt = q.question_type.value if hasattr(q.question_type, "value") else q.question_type
        def _label(raw: str) -> str:
            if qt == "MULTIPLE_CHOICE" and q.options is not None and raw.isdigit() and int(raw) < len(q.options):
                return q.options[int(raw)]
            if qt == "TRUE_FALSE":
                return "True" if raw.strip().lower() == "true" else "False"
            return raw
        distribution = sorted([{
            "answer": raw,
            "label": _label(raw),
            "count": n,
            "is_correct": grade_question(q, raw),
        } for raw, n in counts.items()], key=lambda d: -d["count"])
        wrong = [d for d in distribution if not d["is_correct"]]
        top_wrong = wrong[0] if wrong else None
        out.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "question_type": qt,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "points": q.points,
            "answered": answered,
            "correct": correct,
            "missed": missed,
            "miss_rate": round(missed / answered * 100) if answered else None,
            "answer_distribution": distribution,
            "top_wrong": top_wrong,
            "miss_alerted_at": q.miss_alerted_at.isoformat() if q.miss_alerted_at else None,
        })
    out_sorted = sorted(out, key=lambda r: (r["miss_rate"] is None, -(r["miss_rate"] or 0)))
    return {"exam_id": e.id, "title": e.title, "course_id": e.course_id,
            "total_attempts": len(attempts), "questions": out_sorted}


# ── Iter 53 — CSV export of question insights ────────────────────────
@router.get("/{exam_id}/question-insights.csv")
def exam_question_insights_csv(exam_id: int, db: Session = Depends(get_db),
                               current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Same data as /question-insights, as a CSV for curriculum reviews."""
    import csv
    import io as _io
    from fastapi import Response as _Response
    data = exam_question_insights(exam_id, db=db, current=current)
    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow(["#", "question", "type", "points", "answered", "correct",
                "missed", "miss_rate_pct", "top_wrong_answer",
                "top_wrong_count", "correct_answer"])
    for i, q in enumerate(data["questions"], 1):
        tw = q.get("top_wrong") or {}
        qt = q["question_type"]
        correct_label = q["correct_answer"]
        if qt == "MULTIPLE_CHOICE" and q.get("options") and str(correct_label).isdigit():
            idx = int(correct_label)
            if idx < len(q["options"]):
                correct_label = q["options"][idx]
        w.writerow([i, q["question_text"], qt, q["points"], q["answered"],
                    q["correct"], q["missed"],
                    q["miss_rate"] if q["miss_rate"] is not None else "",
                    tw.get("label", ""), tw.get("count", ""), correct_label])
    filename = f"question-insights-exam-{exam_id}.csv"
    return _Response(buf.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })



# ── AI quiz generator ────────────────────────────────────────────────
from pydantic import BaseModel, Field


class AIQuizRequest(BaseModel):
    course_id: int
    num_questions: int = Field(default=5, ge=1, le=20)
    question_type: Literal["MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER", "MIXED"] = "MULTIPLE_CHOICE"
    avoid_topics: list[str] | None = None


@router.post("/ai-generate-questions")
async def ai_generate_questions(
    body: AIQuizRequest, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles(*INSTRUCTOR_ROLES)),
):
    """Generate exam questions from a course's slide content using the
    Emergent LLM. Returns a preview payload — does NOT persist to the DB."""
    course = db.query(Course).filter(
        Course.id == body.course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    slides = db.query(CourseSlide).filter(CourseSlide.course_id == course.id).order_by(
        CourseSlide.order_index.asc()).all()
    slide_dicts = [{"title": s.title, "content_text": s.content} for s in slides]
    questions = await ai_quiz_service.generate_questions(
        course_title=course.title, slides=slide_dicts,
        num_questions=body.num_questions, question_type=body.question_type,
        avoid_topics=body.avoid_topics,
    )
    from services import audit_service
    audit_service.record(db, current, "AI_QUIZ_GENERATED",
        target_type="course", target_id=str(course.id),
        metadata={"requested": body.num_questions, "returned": len(questions),
                  "type": body.question_type})
    db.commit()
    return {"course_id": course.id, "course_title": course.title, "questions": questions}
