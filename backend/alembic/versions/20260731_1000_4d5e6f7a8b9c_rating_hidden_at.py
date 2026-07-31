"""course_ratings.hidden_at — admin review moderation (Iter 47)

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("course_ratings")]
    if "hidden_at" not in cols:
        op.add_column("course_ratings",
                      sa.Column("hidden_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("course_ratings", "hidden_at")
