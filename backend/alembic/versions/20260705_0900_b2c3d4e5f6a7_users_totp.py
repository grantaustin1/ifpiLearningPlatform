"""Iter 30i — add TOTP-based 2FA columns to users.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-05 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("totp_secret_enc", sa.String(length=500),
                                   nullable=True))
        batch.add_column(sa.Column("totp_enabled_at", sa.DateTime(),
                                   nullable=True))
        batch.add_column(sa.Column("totp_recovery_codes", sa.JSON(),
                                   nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("totp_recovery_codes")
        batch.drop_column("totp_enabled_at")
        batch.drop_column("totp_secret_enc")
