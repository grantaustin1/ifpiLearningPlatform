"""Progress-outbox service (Iter 38 Phase B).

Two entry points:

  enqueue(db, event_type, payload) — called from the hot request path.
    Small INSERT into `progress_outbox`, returns immediately.

  process_batch(db, batch_size=50) — called from the background worker.
    Locks a batch of pending rows using `SELECT ... FOR UPDATE SKIP
    LOCKED` (Postgres) or a plain SELECT with app-level exclusion
    (SQLite). Runs each row's handler, marks it done/failed with
    exponential backoff.

Handlers live in `PROGRESS_HANDLERS` — keyed on event_type. Each is
a function `(db, payload) -> None`. Handlers MUST be idempotent —
the outbox retries failed rows up to `MAX_ATTEMPTS`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import ProgressOutbox

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def enqueue(db: Session, event_type: str, payload: dict) -> int:
    """Insert an outbox row. Returns the outbox id.

    Callers should `db.commit()` on their own — this only calls flush
    so the id is populated in the returned value.
    """
    row = ProgressOutbox(event_type=event_type, payload_json=payload)
    db.add(row)
    db.flush()
    return row.id


def _lock_pending_batch(db: Session, batch_size: int) -> list[ProgressOutbox]:
    """Grab up to `batch_size` pending rows for exclusive processing.

    Postgres path uses `FOR UPDATE SKIP LOCKED` so multiple workers
    never fight over the same row. SQLite falls back to a plain SELECT
    + UPDATE-mark-processing (safe under single-writer).
    """
    now = datetime.now(timezone.utc)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        # Advisory: use skip-locked so multi-worker setups don't collide.
        rows = (db.query(ProgressOutbox)
                .filter(ProgressOutbox.status == "pending",
                        ProgressOutbox.next_attempt_at <= now)
                .order_by(ProgressOutbox.next_attempt_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
                .all())
    else:
        rows = (db.query(ProgressOutbox)
                .filter(ProgressOutbox.status == "pending",
                        ProgressOutbox.next_attempt_at <= now)
                .order_by(ProgressOutbox.next_attempt_at.asc())
                .limit(batch_size)
                .all())
    # Mark as processing so a crashed worker doesn't leave rows stuck.
    for r in rows:
        r.status = "processing"
        r.attempts = (r.attempts or 0) + 1
    return rows


def process_batch(db: Session, batch_size: int = 50) -> tuple[int, int]:
    """Process a batch of pending outbox rows. Returns (ok, failed)."""
    rows = _lock_pending_batch(db, batch_size)
    if not rows:
        return 0, 0
    db.commit()  # flush 'processing' state so restart-recovery can find them

    ok = failed = 0
    for row in rows:
        handler = PROGRESS_HANDLERS.get(row.event_type)
        try:
            if handler is None:
                raise ValueError(f"No handler for event_type={row.event_type!r}")
            handler(db, row.payload_json or {})
            row.status = "done"
            row.processed_at = datetime.now(timezone.utc)
            row.last_error = None
            db.commit()
            ok += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Outbox row %s (%s) failed on attempt %s: %s",
                           row.id, row.event_type, row.attempts, exc)
            row.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
            else:
                # Exponential backoff — 5s * 2^(attempts-1)
                delay = 5 * (2 ** max(0, row.attempts - 1))
                row.status = "pending"
                row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            db.commit()
            failed += 1
    return ok, failed


# ─── Event handlers ───────────────────────────────────────────────────
def _handle_slide_view(db: Session, payload: dict) -> None:
    """Idempotent insert of a SlideView row. Unique constraint on
    (slide, user, day) means duplicates are safely absorbed."""
    from sqlalchemy.exc import IntegrityError
    from models import SlideView
    view = SlideView(
        course_id=payload["course_id"],
        slide_id=payload["slide_id"],
        user_id=payload["user_id"],
        viewed_on_date=payload["viewed_on_date"],
    )
    try:
        db.add(view)
        db.flush()
    except IntegrityError:
        db.rollback()
        # already recorded today — success


PROGRESS_HANDLERS: dict[str, Callable[[Session, dict], None]] = {
    "slide_view": _handle_slide_view,
}
