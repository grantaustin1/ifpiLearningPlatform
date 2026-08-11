"""exam_questions.miss_alerted_at — miss-rate alert dedup (Iter 53)

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "6f7a8b9c0d1e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("exam_questions")]
    if "miss_alerted_at" not in cols:
        op.add_column("exam_questions", sa.Column("miss_alerted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("exam_questions", "miss_alerted_at")
