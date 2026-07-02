"""import jobs table for bulk content migration tracking

Revision ID: e7a3b9c4d816
Revises: d5f0a3bc7e91
Create Date: 2026-06-29 13:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e7a3b9c4d816"
down_revision = "d5f0a3bc7e91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_by_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="PENDING", index=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")
