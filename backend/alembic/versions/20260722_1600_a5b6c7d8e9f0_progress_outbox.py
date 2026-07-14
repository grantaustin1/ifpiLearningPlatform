"""Iter 38 Phase B — progress_outbox table.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-02-12 16:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "progress_outbox" not in insp.get_table_names():
        op.create_table(
            "progress_outbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False,
                      server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("next_attempt_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_progress_outbox_pending",
                        "progress_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "progress_outbox" in insp.get_table_names():
        indexes = {ix["name"] for ix in insp.get_indexes("progress_outbox")}
        if "ix_progress_outbox_pending" in indexes:
            op.drop_index("ix_progress_outbox_pending", table_name="progress_outbox")
        op.drop_table("progress_outbox")
