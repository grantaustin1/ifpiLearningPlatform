"""sso_jti_seen replay-protection table

Revision ID: f1a2b3c4d5e6
Revises: e7a3b9c4d816
Create Date: 2026-06-29 14:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e7a3b9c4d816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "sso_jti_seen" not in insp.get_table_names():
        op.create_table(
            "sso_jti_seen",
            sa.Column("jti", sa.String(120), primary_key=True),
            sa.Column("seen_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
    # Index — guard against re-runs after create_all already made the table
    existing_indexes = {ix["name"] for ix in insp.get_indexes("sso_jti_seen")}
    if "ix_sso_jti_seen_at" not in existing_indexes:
        op.create_index("ix_sso_jti_seen_at", "sso_jti_seen", ["seen_at"])


def downgrade() -> None:
    op.drop_index("ix_sso_jti_seen_at", table_name="sso_jti_seen")
    op.drop_table("sso_jti_seen")
