"""Iter 33 — GDPR + email verification + account deletion

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-02-11 12:00:00.000000

Adds:
- users.email_verified_at (nullable datetime)
- users.deleted_at (nullable datetime) — GDPR soft-delete marker
- email_verification_tokens table
- account_deletion_requests table
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "email_verified_at" not in user_cols:
        op.add_column("users",
                      sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    if "deleted_at" not in user_cols:
        op.add_column("users",
                      sa.Column("deleted_at", sa.DateTime(), nullable=True))

    tables = set(insp.get_table_names())
    if "email_verification_tokens" not in tables:
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("token_hash", sa.String(length=64),
                      unique=True, nullable=False, index=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.current_timestamp()),
        )
    if "account_deletion_requests" not in tables:
        op.create_table(
            "account_deletion_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("code_hash", sa.String(length=64),
                      unique=True, nullable=False, index=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("requested_ip", sa.String(length=45), nullable=True),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.func.current_timestamp()),
        )

    # Backfill: mark all existing pre-verification users as verified so
    # migrations don't lock live prod users out overnight. Post-launch
    # signups will get email_verified_at=NULL correctly.
    bind.execute(sa.text(
        "UPDATE users SET email_verified_at = created_at "
        "WHERE email_verified_at IS NULL"
    ))


def downgrade() -> None:
    op.drop_table("account_deletion_requests")
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "email_verified_at")
