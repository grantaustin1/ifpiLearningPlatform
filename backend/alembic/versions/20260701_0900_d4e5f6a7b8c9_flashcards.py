"""Flashcards + SM-2 review state (Iter 25).

Revision ID: d4e5f6a7b8c9
Revises: c9d2e1f4a5b6
Create Date: 2026-07-01 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c9d2e1f4a5b6"
branch_labels = None
depends_on = None


def _has(insp, table: str) -> bool:
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has(insp, "flashcards"):
        op.create_table(
            "flashcards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=False, index=True),
            sa.Column("slide_id", sa.Integer(),
                      sa.ForeignKey("course_slides.id"), nullable=True),
            sa.Column("front", sa.String(500), nullable=False),
            sa.Column("back", sa.Text(), nullable=False),
            sa.Column("hint", sa.String(300)),
            sa.Column("difficulty", sa.Integer(), nullable=False,
                      server_default=sa.text("2")),
            sa.Column("tags", sa.JSON()),
            sa.Column("generated_by_ai", sa.Boolean(), nullable=False,
                      server_default=sa.text("1")),
            sa.Column("source_chunk_ids", sa.JSON()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_flashcards_org_course", "flashcards",
                        ["organization_id", "course_id"])

    if not _has(insp, "flashcard_reviews"):
        op.create_table(
            "flashcard_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("flashcard_id", sa.Integer(),
                      sa.ForeignKey("flashcards.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("ease_factor", sa.Float(), nullable=False,
                      server_default=sa.text("2.5")),
            sa.Column("interval_days", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("repetitions", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("next_review_at", sa.DateTime(), nullable=False),
            sa.Column("last_quality", sa.Integer()),
            sa.Column("last_reviewed_at", sa.DateTime()),
            sa.Column("review_count", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "flashcard_id",
                                name="uq_review_user_card"),
        )
        op.create_index("ix_reviews_user_next", "flashcard_reviews",
                        ["user_id", "next_review_at"])


def downgrade() -> None:
    op.drop_table("flashcard_reviews")
    op.drop_table("flashcards")
