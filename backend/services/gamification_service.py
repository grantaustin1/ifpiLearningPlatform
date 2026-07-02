"""Gamification: XP, badges, and notifications. Mirrors ERP360 service pattern.

Badges are now stored per-organization in the `badge_tiers` table — admins
can edit labels, emojis, descriptions, thresholds, and ordering from the
/badges page. The legacy `BADGE_META` dict below is the **fallback** used
when an organization has no rows yet (e.g. a brand-new academy in a fresh
test fixture), so the service is never `None`-safe.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models import BadgeTier, Notification, User, UserBadge

XP_FIRST_ENROLLMENT = 10
XP_COURSE_COMPLETE = 50
XP_EXAM_PASS = 100
XP_PERFECT_SCORE_BONUS = 50
XP_FLASHCARD_CORRECT = 2       # per card review with quality >= 3
XP_FLASHCARD_PERFECT = 4       # per card review with quality == 5
XP_DAILY_STREAK_BONUS = 25     # awarded once per new streak day (first review)

# Fallback only. Production lookups go through BadgeTier in the user's org.
BADGE_META = {
    "FIRST_ENROLLMENT": {"label": "First Step",   "emoji": "🎯", "desc": "Enrolled in your first course"},
    "FIRST_COURSE":     {"label": "Graduate",     "emoji": "🎓", "desc": "Completed your first course"},
    "EXAM_PASSER":      {"label": "Scholar",      "emoji": "📚", "desc": "Passed your first exam"},
    "PERFECT_SCORE":    {"label": "Perfectionist","emoji": "💯", "desc": "Scored 100% on an exam"},
    "COURSE_MASTER":    {"label": "Course Master","emoji": "🏆", "desc": "Completed 5 courses"},
}


class GamificationService:
    def __init__(self, db: Session):
        self.db = db

    def award_xp(self, user_id: int, amount: int) -> int:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return 0
        user.points = (user.points or 0) + amount
        self.db.add(user)
        self.db.flush()
        return user.points

    def _tier_meta(self, organization_id: int, slug: str) -> dict:
        """Return badge meta for slug, preferring per-org row over global fallback."""
        row = self.db.query(BadgeTier).filter(
            BadgeTier.organization_id == organization_id,
            BadgeTier.slug == slug,
            BadgeTier.is_active.is_(True),
        ).first()
        if row:
            return {"label": row.label, "emoji": row.emoji or "🏅", "desc": row.description or ""}
        return BADGE_META.get(slug, {"label": slug, "emoji": "🏅", "desc": ""})

    def award_badge(self, user_id: int, badge: str) -> bool:
        """Idempotent — returns True if badge was newly awarded."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        # Allow any DB-defined slug for the user's org, or any fallback slug.
        org_has_slug = self.db.query(BadgeTier).filter(
            BadgeTier.organization_id == user.organization_id,
            BadgeTier.slug == badge, BadgeTier.is_active.is_(True),
        ).first() is not None
        if not org_has_slug and badge not in BADGE_META:
            return False
        existing = self.db.query(UserBadge).filter(
            UserBadge.user_id == user_id, UserBadge.badge == badge
        ).first()
        if existing:
            return False
        self.db.add(UserBadge(user_id=user_id, badge=badge))
        meta = self._tier_meta(user.organization_id, badge)
        self.notify(user_id, "BADGE_EARNED",
                    f"{meta['emoji']} Badge earned: {meta['label']}",
                    meta["desc"], "/profile")
        return True

    def notify(self, user_id: int, type_: str, title: str, message: str,
               link: Optional[str] = None) -> Notification:
        n = Notification(user_id=user_id, type=type_, title=title,
                         message=message, link=link)
        self.db.add(n)
        return n

    # ── Flashcard streak (Iter 25c) ────────────────────────────────
    def compute_flashcard_streak(self, user_id: int) -> dict:
        """Return {current_streak, longest_streak, reviewed_today} — computed
        on demand from FlashcardReview.last_reviewed_at so no schema change
        is needed. A "day" is the UTC calendar day.
        """
        from datetime import datetime, timezone
        from models import FlashcardReview

        rows = self.db.query(FlashcardReview.last_reviewed_at).filter(
            FlashcardReview.user_id == user_id,
            FlashcardReview.last_reviewed_at.isnot(None),
        ).all()
        if not rows:
            return {"current_streak": 0, "longest_streak": 0, "reviewed_today": False}

        # Coerce to UTC date and dedupe
        def _to_utc(dt):
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        days = sorted({_to_utc(r[0]).date() for r in rows}, reverse=True)
        today = datetime.now(timezone.utc).date()
        reviewed_today = today in days

        # Longest streak — walk sorted-desc days looking for consecutive gaps
        longest = current = 1
        for i in range(1, len(days)):
            if (days[i - 1] - days[i]).days == 1:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        # Current streak = consecutive days ending at (today or yesterday)
        from datetime import timedelta
        cursor = today if reviewed_today else (today - timedelta(days=1))
        current_streak = 0
        for d in days:
            if d == cursor:
                current_streak += 1
                cursor -= timedelta(days=1)
            elif d < cursor:
                break
        return {
            "current_streak": current_streak,
            "longest_streak": max(longest, current_streak),
            "reviewed_today": reviewed_today,
        }
