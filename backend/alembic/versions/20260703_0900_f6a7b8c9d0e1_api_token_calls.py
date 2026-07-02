"""API token call log (Iter P2 — token usage analytics).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-03 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "api_token_calls" not in insp.get_table_names():
        op.create_table(
            "api_token_calls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"),
                      nullable=False, index=True),
            sa.Column("api_token_id", sa.Integer(),
                      sa.ForeignKey("api_tokens.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("path", sa.String(300), nullable=False),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("duration_ms", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_token_calls_token_day", "api_token_calls",
                        ["api_token_id", "created_at"])
        op.create_index("ix_token_calls_org_day", "api_token_calls",
                        ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_table("api_token_calls")
