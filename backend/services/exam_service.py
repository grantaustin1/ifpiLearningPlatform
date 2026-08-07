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

        # Iter 53 — Miss-rate alerts for course authors
        try:
            self._check_miss_alerts(exam)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("miss-alert check failed", exc_info=True)

        self.db.commit()
        return {"attempt_id": attempt.id, "score": score, "passed": passed,
                "xp_earned": xp, "badges_earned": badges}

    # ── Iter 53 — Miss-rate alerts ─────────────────────────────────
    MISS_ALERT_THRESHOLD = 50   # percent
    MISS_ALERT_MIN_SAMPLE = 3   # answers needed before alerting

    def _check_miss_alerts(self, exam: Exam) -> None:
        """After an attempt lands, alert org instructors/admins about any
        question whose miss rate is ≥50% across ≥3 answers. Fires once per
        question (`miss_alerted_at` dedup — cleared when the question is
        edited so it can re-alert if the fix didn't help)."""
        from models import User, UserRole
        from services.mail_service import MailService

        candidates = [q for q in exam.questions if q.miss_alerted_at is None]
        if not candidates:
            return
        attempts = self.db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam.id, ExamAttempt.answers.isnot(None),
        ).all()
        flagged = []
        for q in candidates:
            answered = correct = 0
            for a in attempts:
                ans = (a.answers or {}).get(str(q.id))
                if ans is None or ans == "":
                    continue
                answered += 1
                if grade_question(q, ans):
                    correct += 1
            if answered < self.MISS_ALERT_MIN_SAMPLE:
                continue
            miss_rate = round((answered - correct) / answered * 100)
            if miss_rate >= self.MISS_ALERT_THRESHOLD:
                q.miss_alerted_at = datetime.now(timezone.utc)
                flagged.append((q, miss_rate, answered))
        if not flagged:
            return

        managers = (self.db.query(User)
                    .join(UserRole, UserRole.user_id == User.id)
                    .filter(User.organization_id == exam.organization_id,
                            User.is_active.is_(True),
                            UserRole.role.in_(["INSTRUCTOR", "ADMIN", "SUPER_ADMIN"]))
                    .distinct().all())
        gam = GamificationService(self.db)
        mail = MailService(self.db)
        for q, miss_rate, answered in flagged:
            snippet = q.question_text if len(q.question_text) <= 80 else q.question_text[:79] + "…"
            for m in managers:
                gam.notify(
                    m.id, "QUESTION_MISS_ALERT",
                    f"⚠️ {miss_rate}% miss rate on \"{exam.title}\"",
                    f'Learners keep missing: "{snippet}" ({miss_rate}% of {answered} answers wrong). '
                    f"Review the question or its course content.",
                    "/exams",
                )
                try:
                    mail.send_email(
                        to_email=m.email, to_name=m.name,
                        subject=f"⚠️ Question needs attention on {exam.title}",
                        body_html=(
                            f"<div style='font-family:system-ui,sans-serif;max-width:560px'>"
                            f"<h2 style='color:#b45309;margin:0 0 12px'>High miss rate detected</h2>"
                            f"<p><strong>{miss_rate}%</strong> of {answered} answers to this question on "
                            f"<strong>{exam.title}</strong> are wrong:</p>"
                            f"<blockquote style='border-left:3px solid #f59e0b;margin:12px 0;"
                            f"padding:8px 14px;background:#fffbeb;color:#78350f'>{q.question_text}</blockquote>"
                            f"<p>Open the exam's <em>Question insights</em> tab to review distractor stats "
                            f"and edit the question or its course content.</p></div>"
                        ),
                        body_text=(f"{miss_rate}% of {answered} answers to '{q.question_text}' on "
                                   f"'{exam.title}' are wrong. Review it in Question insights."),
                        template="question_miss_alert",
                        organization_id=exam.organization_id, user_id=m.id,
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).warning("miss-alert email failed", exc_info=True)
