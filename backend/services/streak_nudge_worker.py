"""Iter 27 — Streak-break nudge worker.

Detects learners who had a `>=3-day` learning streak, missed today, and
have not been nudged in the last 24h. Creates an in-app Notification
row that surfaces on the bell icon + also flags the streak-nudge column
for de-dup.

The heavy lifting (streak computation) lives in
`services.gamification_service.compute_learning_streak`. This worker is
a thin driver: iterate active users, compute streak, decide, emit.

Runs once every 6 hours. Safe to run more often — the
`streak_nudge_last_sent_at` timestamp guards against duplicates.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from core.database import SessionLocal
from models import Notification, User
from services.gamification_service import GamificationService

logger = logging.getLogger(__name__)

STREAK_NUDGE_THRESHOLD = 3       # only nudge users who had 3+ day streaks
STREAK_NUDGE_COOLDOWN_HRS = 22   # dedup window ~1 day (loose so job can retry)


def run_streak_nudge_pass() -> dict:
    """Scan all users, nudge those whose streak just broke today.

    Returns a stats dict for logging. Non-destructive — never raises."""
    stats = {"scanned": 0, "eligible": 0, "notified": 0, "skipped_cooldown": 0}
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cooldown = now - timedelta(hours=STREAK_NUDGE_COOLDOWN_HRS)
        # Only consider learners (roles handled implicitly — any user
        # with slide-view/flashcard history qualifies).
        users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
        gam = GamificationService(db)
        for u in users:
            stats["scanned"] += 1
            try:
                s = gam.compute_learning_streak(u.id)
            except Exception:
                continue
            # Only nudge if: had a real streak AND missed today
            if s["current_streak"] < STREAK_NUDGE_THRESHOLD:
                continue
            if s["active_today"]:
                continue
            stats["eligible"] += 1
            if u.streak_nudge_last_sent_at:
                # SQLite strips tz — normalise both sides to naive UTC
                last = u.streak_nudge_last_sent_at
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if last > cooldown:
                    stats["skipped_cooldown"] += 1
                    continue
            # Emit in-app notification
            note = Notification(
                user_id=u.id,
                type="STREAK_NUDGE",
                title="Keep your streak alive!",
                message=(
                    f"You're on a {s['current_streak']}-day learning "
                    "streak — jump into a slide today to keep it going."
                ),
                link="/courses",
            )
            db.add(note)
            u.streak_nudge_last_sent_at = now
            stats["notified"] += 1
        db.commit()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("streak-nudge worker failed: %s", e)
        db.rollback()
    finally:
        db.close()
    return stats


def _tick() -> None:  # scheduler entrypoint
    try:
        stats = run_streak_nudge_pass()
        if stats.get("notified", 0) > 0:
            logger.info("streak-nudge: %s", stats)
    except Exception as e:  # pragma: no cover
        logger.exception("streak-nudge tick failed: %s", e)
