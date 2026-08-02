"""courses.is_featured flag

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-30
"""
import sqlalchemy as sa
from alembic import op

revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("courses")}
    if "is_featured" in cols:
        return  # idempotent — dev create_all may have added it
    op.add_column("courses", sa.Column("is_featured", sa.Boolean(),
                                       nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("courses", "is_featured")
