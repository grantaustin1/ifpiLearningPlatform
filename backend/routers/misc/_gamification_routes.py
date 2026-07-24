from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import EnrollmentStatus, User, UserBadge
from schemas import LeaderboardEntry
from services.gamification_service import BADGE_META

from . import gam_router


@gam_router.get("/leaderboard", response_model=List[LeaderboardEntry])
def leaderboard(cohort: Optional[str] = None,
                db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    # Iter 38 — was 103 queries via lazy-load of `enrollments` and
    # `badges` for each of 50 users. `selectinload` collapses to 3
    # queries total.
    q = (db.query(User)
         .options(selectinload(User.enrollments), selectinload(User.badges))
         .filter(User.organization_id == current.organization_id,
                 User.is_active.is_(True)))
    if cohort:
        q = q.filter(User.cohort == cohort)
    rows = q.order_by(desc(User.points)).limit(50).all()
    out = []
    for u in rows:
        completed = sum(1 for e in u.enrollments if e.status == EnrollmentStatus.COMPLETED)
        out.append(LeaderboardEntry(
            user_id=u.id, name=u.name, points=u.points or 0,
            badges=len(u.badges), completed=completed,
        ))
    return out


@gam_router.get("/me")
def my_gamification(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current.id).first()
    # Resolve badge meta from per-org BadgeTier rows (with global fallback)
    from models import BadgeTier
    tiers = {t.slug: t for t in db.query(BadgeTier).filter(
        BadgeTier.organization_id == current.organization_id,
        BadgeTier.is_active.is_(True),
    ).all()}
    def _meta(slug: str) -> dict:
        t = tiers.get(slug)
        if t:
            return {"label": t.label, "emoji": t.emoji or "🏅", "desc": t.description or ""}
        return BADGE_META.get(slug, {"label": slug, "emoji": "🏅", "desc": ""})
    badges = [{
        "badge": b.badge, "earned_at": b.earned_at, "meta": _meta(b.badge),
    } for b in user.badges]
    rank = db.query(User).filter(
        User.organization_id == current.organization_id,
        User.points > (user.points or 0),
    ).count() + 1
    total = db.query(User).filter(
        User.organization_id == current.organization_id, User.is_active.is_(True),
    ).count()
    return {"points": user.points or 0, "badges": badges, "rank": rank, "total": total}


@gam_router.get("/preferences")
def get_gamification_preferences(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 31 — per-user gamification preferences."""
    user = db.query(User).filter(User.id == current.id).first()
    return {
        "streak_digest_enabled": bool(user.streak_digest_enabled)
        if user else True,
    }


@gam_router.patch("/preferences")
def update_gamification_preferences(
    body: dict,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 31 — toggle weekly streak digest opt-in/out."""
    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if "streak_digest_enabled" in body:
        user.streak_digest_enabled = bool(body["streak_digest_enabled"])
    db.commit()
    return {"streak_digest_enabled": bool(user.streak_digest_enabled)}


@gam_router.get("/learning-streak")
def learning_streak(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 26 — Consecutive-day learning streak. A day counts when the
    learner viewed a course slide OR reviewed a flashcard. Returns
    `{current_streak, longest_streak, active_today, last_active_date}`."""
    from services.gamification_service import GamificationService
    return GamificationService(db).compute_learning_streak(current.id)


@gam_router.get("/streak-leaderboard")
def streak_leaderboard(
    limit: int = 10,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Iter 28 — Org-wide "top streaks this week" leaderboard.

    Ranks the top `limit` learners in the caller's organisation by
    current streak (descending). Ties break on longest_streak, then
    user id. Includes the caller's own rank at the bottom even if
    they're outside the top N.

    Cheap enough to compute on the fly for orgs up to a few hundred
    active users (SlideView + FlashcardReview joins are already
    indexed). For much larger orgs, pre-computing in a nightly job
    would be advisable — but iter-28 scope is small orgs.
    """
    from services.gamification_service import GamificationService
    limit = max(1, min(limit, 50))
    gam = GamificationService(db)
    users = db.query(User).filter(
        User.organization_id == current.organization_id,
        User.is_active == True,  # noqa: E712
    ).all()

    entries = []
    for u in users:
        try:
            s = gam.compute_learning_streak(u.id)
        except Exception:
            continue
        if s["current_streak"] <= 0 and s["longest_streak"] <= 0:
            continue  # skip users with no activity — cleaner UX
        entries.append({
            "user_id": u.id,
            "name": u.name or u.email.split("@")[0],
            "avatar_url": None,  # Iter 29 backlog — org-scoped avatars
            "current_streak": s["current_streak"],
            "longest_streak": s["longest_streak"],
            "active_today": s["active_today"],
            "is_you": u.id == current.id,
        })
    entries.sort(key=lambda e: (
        -e["current_streak"], -e["longest_streak"], e["user_id"],
    ))

    top = entries[:limit]
    caller_rank = next(
        (i + 1 for i, e in enumerate(entries) if e["user_id"] == current.id),
        None,
    )
    return {
        "top": top,
        "your_rank": caller_rank,
        "your_entry": next((e for e in entries if e["is_you"]), None),
        "total_participants": len(entries),
    }
