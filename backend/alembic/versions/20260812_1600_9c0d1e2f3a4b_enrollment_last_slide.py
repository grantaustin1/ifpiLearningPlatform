"""enrollments.last_slide_index — resume where the learner left off

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "9c0d1e2f3a4b"
down_revision = "8b9c0d1e2f3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("enrollments")]
    if "last_slide_index" not in cols:
        op.add_column("enrollments",
                      sa.Column("last_slide_index", sa.Integer(), nullable=True,
                                server_default="0"))


def downgrade() -> None:
    op.drop_column("enrollments", "last_slide_index")
