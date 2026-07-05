"""Iter 24 — Marketplace funnel analytics + Live-session occurrence cancel.

Adds:
1. `course_views` table — one row per (user OR anon-hash, course, day)
   marketplace detail page impression. Feeds the funnel analytics panel.
2. `live_sessions.cancelled_at` (nullable DateTime) — enables EXDATE
   semantics: an admin can cancel a single occurrence of a recurring
   series without destroying the series' materialised children.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if "course_views" not in _tables():
        op.create_table(
            "course_views",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=False),
            sa.Column("viewer_key", sa.String(80), nullable=False),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("referrer", sa.String(500), nullable=True),
            sa.Column("viewed_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("viewed_on_date", sa.String(10), nullable=False),
            sa.UniqueConstraint("course_id", "viewer_key", "viewed_on_date",
                                name="uq_course_view_unique_per_day"),
        )
        op.create_index("ix_course_views_course_id", "course_views", ["course_id"])
        op.create_index("ix_course_views_viewer_key", "course_views", ["viewer_key"])
        op.create_index("ix_course_views_user_id", "course_views", ["user_id"])
        op.create_index("ix_course_views_viewed_on_date", "course_views", ["viewed_on_date"])
        op.create_index("ix_course_views_course_day", "course_views",
                        ["course_id", "viewed_on_date"])

    if not _has_column("live_sessions", "cancelled_at"):
        with op.batch_alter_table("live_sessions") as batch:
            batch.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    if "course_views" in _tables():
        op.drop_table("course_views")
    if _has_column("live_sessions", "cancelled_at"):
        with op.batch_alter_table("live_sessions") as batch:
            batch.drop_column("cancelled_at")
