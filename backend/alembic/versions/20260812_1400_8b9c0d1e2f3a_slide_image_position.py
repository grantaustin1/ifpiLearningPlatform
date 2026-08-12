"""course_slides.image_position — image layout relative to slide text

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "8b9c0d1e2f3a"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("course_slides")]
    if "image_position" not in cols:
        op.add_column("course_slides",
                      sa.Column("image_position", sa.String(10), nullable=True,
                                server_default="above"))


def downgrade() -> None:
    op.drop_column("course_slides", "image_position")
