"""course_slides.media_opacity — image/video transparency (20-100%)

Revision ID: a0d1e2f3a4b5
Revises: 9c0d1e2f3a4b
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "a0d1e2f3a4b5"
down_revision = "9c0d1e2f3a4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("course_slides")]
    if "media_opacity" not in cols:
        op.add_column("course_slides",
                      sa.Column("media_opacity", sa.Integer(), nullable=True,
                                server_default="100"))


def downgrade() -> None:
    op.drop_column("course_slides", "media_opacity")
