"""SCORM packages, xAPI statements, slide versioning (Iter 18 + 19)

Revision ID: a8b4c9d3e7f2
Revises: f1a2b3c4d5e6
Create Date: 2026-06-29 15:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a8b4c9d3e7f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _has(insp, table: str) -> bool:
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has(insp, "scorm_packages"):
        op.create_table(
            "scorm_packages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=True, index=True),
            sa.Column("slide_id", sa.Integer(),
                      sa.ForeignKey("course_slides.id"), nullable=True, index=True),
            sa.Column("manifest_title", sa.String(300)),
            sa.Column("launch_url", sa.String(800), nullable=False),
            sa.Column("scorm_version", sa.String(16)),
            sa.Column("package_dir", sa.String(800), nullable=False),
            sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )

    if not _has(insp, "xapi_statements"):
        op.create_table(
            "xapi_statements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("actor_email", sa.String(200), index=True),
            sa.Column("verb", sa.String(120), nullable=False),
            sa.Column("object_id", sa.String(500)),
            sa.Column("result", sa.JSON()),
            sa.Column("raw", sa.JSON(), nullable=False),
            sa.Column("stored_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_xapi_org_user_stored", "xapi_statements",
                        ["organization_id", "user_id", "stored_at"])
        op.create_index("ix_xapi_verb_stored", "xapi_statements",
                        ["verb", "stored_at"])

    if not _has(insp, "slide_versions"):
        op.create_table(
            "slide_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slide_id", sa.Integer(),
                      sa.ForeignKey("course_slides.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("content", sa.Text()),
            sa.Column("slide_type", sa.String(20)),
            sa.Column("media_url", sa.String(500)),
            sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("change_summary", sa.String(200)),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_slide_versions_slide_ver", "slide_versions",
                        ["slide_id", "version_number"])


def downgrade() -> None:
    op.drop_table("slide_versions")
    op.drop_table("xapi_statements")
    op.drop_table("scorm_packages")
