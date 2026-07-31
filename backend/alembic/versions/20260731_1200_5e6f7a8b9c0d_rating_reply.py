"""course_ratings reply columns — academy replies to reviews (Iter 48)

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("course_ratings")]
    if "reply_text" not in cols:
        op.add_column("course_ratings", sa.Column("reply_text", sa.Text()))
    if "reply_at" not in cols:
        op.add_column("course_ratings", sa.Column("reply_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("course_ratings", "reply_at")
    op.drop_column("course_ratings", "reply_text")
