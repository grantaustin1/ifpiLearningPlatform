"""Iter 32 — must_change_password + password_reset_tokens

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-02-11 10:00:00.000000

Adds:
- `users.must_change_password` (bool, default False) — foot-gun guard
  for the seeded admin@ifpi.org account. Migration flips the flag ON
  for the seeded admin row so shipping with `admin123` is impossible.
- `password_reset_tokens` table backing the /api/auth/forgot-password
  + /api/auth/reset-password flow.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: server.py runs `Base.metadata.create_all` at boot on
    # SQLite, so the columns/tables may already exist. Inspect first.
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)

    existing_user_cols = {c["name"] for c in insp.get_columns("users")}
    if "must_change_password" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column("must_change_password", sa.Boolean(), nullable=False,
                      server_default=sa.text("0")),
        )

    existing_tables = set(insp.get_table_names())
    if "password_reset_tokens" not in existing_tables:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("token_hash", sa.String(length=64), nullable=False,
                      unique=True, index=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("requested_ip", sa.String(length=45), nullable=True),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.current_timestamp()),
        )

    # Flip the seeded admin@ifpi.org to must_change_password=True.
    bind.execute(sa.text(
        "UPDATE users SET must_change_password = 1 "
        "WHERE email = 'admin@ifpi.org'"
    ))


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "must_change_password")
