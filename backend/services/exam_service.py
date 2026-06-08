"""Exam grading service — handles attempt submission, scoring, gamification hooks."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Exam, ExamAttempt, ExamQuestion, QuestionType
from services.gamification_service import (
    XP_EXAM_PASS, XP_PERFECT_SCORE_BONUS, GamificationService,
)


def _normalize_answer(a: str) -> str:
    return (a or "").strip().lower()


def grade_question(q: ExamQuestion, user_answer: str) -> bool:
    """Single-question grading with consistent normalization across all types."""
    ua = _normalize_answer(user_answer)
    ca = _normalize_answer(q.correct_answer)
    if not ua:
        return False
    if q.question_type == QuestionType.MULTIPLE_CHOICE:
        # Accept either the option index ("0") or the option text
        if ua == ca:
            return True
        if q.options and ca.isdigit():
            idx = int(ca)
            if 0 <= idx < len(q.options):
                return ua == _normalize_answer(q.options[idx])
        return False
    if q.question_type == QuestionType.TRUE_FALSE:
        # Accept "true"/"false", "0"/"1", or the literal
        truthy = {"true", "1", "t", "yes", "y"}
        falsy = {"false", "0", "f", "no", "n"}
        def bucket(s: str):
            if s in truthy:
                return True
            if s in falsy:
                return False
            return None
        return bucket(ua) is not None and bucket(ua) == bucket(ca)
    # FILL_IN_BLANK / SHORT_ANSWER → case-insensitive exact match
    return ua == ca


class ExamService:
    def __init__(self, db: Session):
        self.db = db

    def get_exam(self, exam_id: int, organization_id: int) -> Exam:
        exam = self.db.query(Exam).filter(
            Exam.id == exam_id, Exam.organization_id == organization_id,
        ).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")
        return exam

    def submit_attempt(self, exam_id: int, user_id: int,
                       organization_id: int, answers: Dict[str, str]) -> dict:
        exam = self.get_exam(exam_id, organization_id)
        # Attempt cap
        prior = self.db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == user_id,
        ).count()
        if prior >= exam.max_attempts:
            raise HTTPException(status_code=400, detail="Maximum attempts reached")

        total_points, earned = 0, 0
        for q in exam.questions:
            total_points += q.points
            if grade_question(q, answers.get(str(q.id), "")):
                earned += q.points

        score = round((earned / total_points) * 100) if total_points else 0
        passed = score >= exam.passing_score

        attempt = ExamAttempt(
            exam_id=exam.id, user_id=user_id, score=score, passed=passed,
            answers=answers, completed_at=datetime.now(timezone.utc),
        )
        self.db.add(attempt)
        self.db.flush()

        xp, badges = 0, []
        gam = GamificationService(self.db)
        if passed:
            xp += XP_EXAM_PASS
            if score == 100:
                xp += XP_PERFECT_SCORE_BONUS
            gam.award_xp(user_id, xp)
            gam.notify(user_id, "EXAM_RESULT",
                       f"✅ Passed: {exam.title}",
                       f"You scored {score}% and earned {xp} XP!",
                       "/exams")
            pass_count = self.db.query(ExamAttempt).filter(
                ExamAttempt.user_id == user_id, ExamAttempt.passed.is_(True),
            ).count()
            if pass_count == 1 and gam.award_badge(user_id, "EXAM_PASSER"):
                badges.append("EXAM_PASSER")
            if score == 100 and gam.award_badge(user_id, "PERFECT_SCORE"):
                badges.append("PERFECT_SCORE")
        else:
            gam.notify(user_id, "EXAM_RESULT",
                       f"❌ {exam.title} — keep trying",
                       f"You scored {score}%. Pass mark is {exam.passing_score}%.",
                       "/exams")

        self.db.commit()
        return {"attempt_id": attempt.id, "score": score, "passed": passed,
                "xp_earned": xp, "badges_earned": badges}
