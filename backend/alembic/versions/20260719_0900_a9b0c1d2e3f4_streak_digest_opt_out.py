"""Iter 31 — user-level streak digest opt-out preference.

Adds:
- `users.streak_digest_enabled` — default True. When False, the
  weekly streak-digest worker skips this user.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-04 06:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column(
            "streak_digest_enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("1"),
        ))


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("streak_digest_enabled")
