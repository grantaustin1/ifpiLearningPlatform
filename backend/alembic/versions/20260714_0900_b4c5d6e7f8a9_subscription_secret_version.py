"""Iter 25 — Marketplace analytics roll-up columns + subscription secret
version + placeholder for QR code (no DB change; QR is derived at request
time from the token).

Adds `organizations.subscription_secret_version` (default 1). Bumping
this via `POST /api/live-sessions/subscribe-url/rotate` invalidates all
outstanding calendar-subscription URLs for the org WITHOUT logging out
active users (which JWT_SECRET rotation would do).

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if not _has_column("organizations", "subscription_secret_version"):
        with op.batch_alter_table("organizations") as batch:
            batch.add_column(
                sa.Column("subscription_secret_version", sa.Integer(),
                          nullable=False, server_default="1"),
            )


def downgrade() -> None:
    if _has_column("organizations", "subscription_secret_version"):
        with op.batch_alter_table("organizations") as batch:
            batch.drop_column("subscription_secret_version")
