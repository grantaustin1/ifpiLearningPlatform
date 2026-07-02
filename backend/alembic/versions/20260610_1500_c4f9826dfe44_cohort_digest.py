"""per-tenant cohort digest opt-in + last-sent tracking

Revision ID: c4f9826dfe44
Revises: b3d8915cef27
Create Date: 2026-06-10 15:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4f9826dfe44"
down_revision = "b3d8915cef27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as bop:
        bop.add_column(sa.Column("cohort_digest_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        bop.add_column(sa.Column("cohort_digest_last_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as bop:
        bop.drop_column("cohort_digest_last_sent_at")
        bop.drop_column("cohort_digest_enabled")
