"""webhook subscriptions + delivery log

Revision ID: d5f0a3bc7e91
Revises: c4f9826dfe44
Create Date: 2026-06-29 12:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d5f0a3bc7e91"
down_revision = "c4f9826dfe44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("target_url", sa.String(500), nullable=False),
        sa.Column("secret", sa.String(120), nullable=False),
        sa.Column("events", sa.Text(), nullable=False),  # JSON list of event_type strings
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(),
                  sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("event_type", sa.String(80), nullable=False, index=True),
        sa.Column("event_id", sa.String(80), nullable=False),  # uuid for dedup on receiver
        sa.Column("payload", sa.Text(), nullable=False),       # JSON body
        sa.Column("signature", sa.String(80), nullable=False), # hex HMAC-SHA256
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        # QUEUED → DELIVERED | FAILED | DEAD_LETTER
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
