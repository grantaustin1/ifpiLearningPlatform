"""API tokens migration (Iter 21)

Revision ID: b1c2d3e4f5a6
Revises: a8b4c9d3e7f2
Create Date: 2026-06-29 16:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a8b4c9d3e7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "api_tokens" in insp.get_table_names():
        return
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False, index=True),
        sa.Column("token_hash", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("scopes", sa.JSON()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_used_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_tokens_org_active", "api_tokens",
                    ["organization_id", "is_active"])


def downgrade() -> None:
    op.drop_table("api_tokens")
