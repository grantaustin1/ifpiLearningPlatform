"""tester_feedback.screenshot_url — feedback screenshot attachments

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "7a8b9c0d1e2f"
down_revision = "6f7a8b9c0d1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("tester_feedback")]
    if "screenshot_url" not in cols:
        op.add_column("tester_feedback", sa.Column("screenshot_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("tester_feedback", "screenshot_url")
