"""Iter 30s — Affiliate / referral program tables.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def _existing() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing()
    if "affiliate_codes" not in existing:
        op.create_table(
            "affiliate_codes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("code", sa.String(40), nullable=False, unique=True),
            sa.Column("reward_bps", sa.Integer(), nullable=False,
                      server_default="1000"),
            sa.Column("cap_credits_cents", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_affiliate_codes_organization_id",
                        "affiliate_codes", ["organization_id"])
        op.create_index("ix_affiliate_codes_code",
                        "affiliate_codes", ["code"])
    if "affiliate_referrals" not in existing:
        op.create_table(
            "affiliate_referrals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code_id", sa.Integer(),
                      sa.ForeignKey("affiliate_codes.id"), nullable=False),
            sa.Column("referred_organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("signed_up_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("credit_cents", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="PENDING"),
            sa.Column("credited_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.UniqueConstraint("code_id", "referred_organization_id",
                                name="uq_referral_code_org"),
        )
        op.create_index("ix_affiliate_referrals_code_id",
                        "affiliate_referrals", ["code_id"])
        op.create_index("ix_affiliate_referrals_referred_organization_id",
                        "affiliate_referrals", ["referred_organization_id"])
        op.create_index("ix_affiliate_referrals_status",
                        "affiliate_referrals", ["status"])


def downgrade() -> None:
    existing = _existing()
    for tbl in ("affiliate_referrals", "affiliate_codes"):
        if tbl in existing:
            op.drop_table(tbl)
