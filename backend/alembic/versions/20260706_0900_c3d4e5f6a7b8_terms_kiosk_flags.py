"""Iter 30l — T&Cs versions/acceptances + kiosk settings + feature flags.

Idempotent: startup calls `Base.metadata.create_all(checkfirst=True)`
in dev which may create these tables before alembic runs. Migration
skips create_table when the table already exists so `alembic upgrade`
succeeds in both fresh-CI and warm-dev environments.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "terms_versions" not in existing:
        op.create_table(
            "terms_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("title", sa.String(255), nullable=False,
                      server_default="Terms of Service"),
            sa.Column("body_markdown", sa.Text(), nullable=False,
                      server_default=""),
            sa.Column("is_current", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("published_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id")),
            sa.Column("published_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_terms_versions_organization_id",
                        "terms_versions", ["organization_id"])
        op.create_index("ix_terms_versions_is_current",
                        "terms_versions", ["is_current"])
        op.create_index("ix_terms_org_version",
                        "terms_versions", ["organization_id", "version"])

    if "terms_acceptances" not in existing:
        op.create_table(
            "terms_acceptances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("terms_version_id", sa.Integer(),
                      sa.ForeignKey("terms_versions.id"), nullable=False),
            sa.Column("accepted_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("ip_address", sa.String(45)),
            sa.Column("user_agent", sa.String(500)),
            sa.UniqueConstraint("user_id", "terms_version_id",
                                name="uq_terms_ack"),
        )
        op.create_index("ix_terms_acceptances_user_id",
                        "terms_acceptances", ["user_id"])
        op.create_index("ix_terms_acceptances_terms_version_id",
                        "terms_acceptances", ["terms_version_id"])

    if "kiosk_settings" not in existing:
        op.create_table(
            "kiosk_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False,
                      unique=True),
            sa.Column("enabled", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("idle_timeout_seconds", sa.Integer(), nullable=False,
                      server_default="300"),
            sa.Column("unlock_pin_hash", sa.String(200)),
            sa.Column("updated_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )

    if "feature_flags" not in existing:
        op.create_table(
            "feature_flags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("flag_key", sa.String(80), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
            sa.Column("note", sa.String(500)),
            sa.Column("updated_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.UniqueConstraint("organization_id", "flag_key",
                                name="uq_flag_org_key"),
        )
        op.create_index("ix_feature_flags_organization_id",
                        "feature_flags", ["organization_id"])
        op.create_index("ix_feature_flags_flag_key",
                        "feature_flags", ["flag_key"])


def downgrade() -> None:
    existing = _existing_tables()
    for tbl in ("feature_flags", "kiosk_settings",
                "terms_acceptances", "terms_versions"):
        if tbl in existing:
            op.drop_table(tbl)
