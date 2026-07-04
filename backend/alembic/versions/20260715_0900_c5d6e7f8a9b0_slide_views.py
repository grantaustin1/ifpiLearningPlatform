"""Iter 26 — Slide-level drop-off analytics.

Adds `slide_views` table — per (slide, user, day) view impression for
the course player. Powers the drop-off heatmap on the Course Edit page.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "slide_views" not in _tables():
        op.create_table(
            "slide_views",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=False),
            sa.Column("slide_id", sa.Integer(),
                      sa.ForeignKey("course_slides.id"), nullable=False),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("viewed_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("viewed_on_date", sa.String(10), nullable=False),
            sa.UniqueConstraint("slide_id", "user_id", "viewed_on_date",
                                name="uq_slide_view_per_user_per_day"),
        )
        op.create_index("ix_slide_views_course_id", "slide_views", ["course_id"])
        op.create_index("ix_slide_views_slide_id", "slide_views", ["slide_id"])
        op.create_index("ix_slide_views_user_id", "slide_views", ["user_id"])
        op.create_index("ix_slide_views_viewed_on_date", "slide_views", ["viewed_on_date"])
        op.create_index("ix_slide_views_course_slide", "slide_views",
                        ["course_id", "slide_id"])


def downgrade() -> None:
    if "slide_views" in _tables():
        op.drop_table("slide_views")
