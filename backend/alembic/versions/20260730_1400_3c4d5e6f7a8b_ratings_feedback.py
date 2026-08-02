"""course ratings + tester feedback tables

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-07-30
"""
import sqlalchemy as sa
from alembic import op

revision = "3c4d5e6f7a8b"
down_revision = "2b3c4d5e6f7a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "course_ratings" not in tables:
        op.create_table(
            "course_ratings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"),
                      nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("course_id", "user_id", name="uq_course_rating_user"),
        )
    if "tester_feedback" not in tables:
        op.create_table(
            "tester_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("page", sa.String(300)),
            sa.Column("category", sa.String(30), server_default="BUG"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="NEW"),
            sa.Column("created_at", sa.DateTime()),
        )


def downgrade() -> None:
    op.drop_table("tester_feedback")
    op.drop_table("course_ratings")
