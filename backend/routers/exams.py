"""Exam routes: CRUD + question management + take + attempt submission."""
from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from core.role_registry import INSTRUCTOR_ROLES
from models import Course, CourseSlide, Exam, ExamAttempt, ExamQuestion, QuestionType
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
    return user.has_any_role(INSTRUCTOR_ROLES)


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
