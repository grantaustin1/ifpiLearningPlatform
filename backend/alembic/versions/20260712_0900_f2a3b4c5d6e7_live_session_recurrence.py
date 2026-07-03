"""Iter 23 — Live Session recurrence + reminder tracking.

Adds three columns to `live_sessions`:
- `recurrence_rule` (String(500)) — iCal RRULE, e.g. `FREQ=WEEKLY;COUNT=8`.
  Present only on the "series head"; expanded child instances have this
  column NULL.
- `parent_series_id` (Integer FK → live_sessions.id) — points from a
  materialised occurrence back to the series head, so we can bulk-cancel
  a whole series without hunting.
- `reminder_sent_at` (DateTime) — set by the 15-min reminder worker
  after it enqueues the email to all RSVPs, so we never spam twice.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    with op.batch_alter_table("live_sessions") as batch:
        if not _has_column("live_sessions", "recurrence_rule"):
            batch.add_column(sa.Column("recurrence_rule", sa.String(500), nullable=True))
        if not _has_column("live_sessions", "parent_series_id"):
            batch.add_column(sa.Column("parent_series_id", sa.Integer(), nullable=True))
        if not _has_column("live_sessions", "reminder_sent_at"):
            batch.add_column(sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))
    # Index for the reminder worker's query (WHERE reminder_sent_at IS NULL AND start_at BETWEEN ...)
    op.create_index("ix_live_sessions_reminder", "live_sessions",
                    ["reminder_sent_at", "start_at"])
    op.create_index("ix_live_sessions_parent_series_id", "live_sessions",
                    ["parent_series_id"])


def downgrade() -> None:
    op.drop_index("ix_live_sessions_reminder", table_name="live_sessions")
    op.drop_index("ix_live_sessions_parent_series_id", table_name="live_sessions")
    with op.batch_alter_table("live_sessions") as batch:
        if _has_column("live_sessions", "recurrence_rule"):
            batch.drop_column("recurrence_rule")
        if _has_column("live_sessions", "parent_series_id"):
            batch.drop_column("parent_series_id")
        if _has_column("live_sessions", "reminder_sent_at"):
            batch.drop_column("reminder_sent_at")
