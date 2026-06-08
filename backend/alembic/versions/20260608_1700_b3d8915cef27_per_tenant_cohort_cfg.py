"""per-tenant cohort threshold + webhook

Revision ID: b3d8915cef27
Revises: a9c2470b8e15
Create Date: 2026-02-08 17:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b3d8915cef27"
down_revision = "a9c2470b8e15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as bop:
        bop.add_column(sa.Column("cohort_threshold", sa.Integer(), nullable=False, server_default="75"))
        bop.add_column(sa.Column("cohort_celebration_webhook_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as bop:
        bop.drop_column("cohort_celebration_webhook_url")
        bop.drop_column("cohort_threshold")
