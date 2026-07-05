"""Iter 22 — Marketplace opt-in flag on organizations.

When true, an org's PUBLISHED courses appear in the cross-tenant public
marketplace (/api/catalog, /marketplace UI). Default true so seeded IFPI
Main Academy is discoverable out-of-the-box; admins can opt out via
`PATCH /api/organization {marketplace_opt_in: false}`.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if not _has_column("organizations", "marketplace_opt_in"):
        with op.batch_alter_table("organizations") as batch:
            batch.add_column(
                sa.Column("marketplace_opt_in", sa.Boolean(),
                          nullable=False, server_default=sa.text("1")),
            )


def downgrade() -> None:
    if _has_column("organizations", "marketplace_opt_in"):
        with op.batch_alter_table("organizations") as batch:
            batch.drop_column("marketplace_opt_in")
