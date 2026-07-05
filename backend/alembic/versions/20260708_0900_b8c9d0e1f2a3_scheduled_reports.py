"""Iter 30p — Scheduled Reports table.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-08 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _existing() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "scheduled_reports" in _existing():
        return
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("report_kind", sa.String(50), nullable=False),
        sa.Column("cadence", sa.String(20), nullable=False),
        sa.Column("recipient_emails", sa.JSON(), nullable=False,
                  server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_scheduled_reports_organization_id",
                    "scheduled_reports", ["organization_id"])
    op.create_index("ix_scheduled_reports_created_by_user_id",
                    "scheduled_reports", ["created_by_user_id"])


def downgrade() -> None:
    if "scheduled_reports" in _existing():
        op.drop_table("scheduled_reports")
