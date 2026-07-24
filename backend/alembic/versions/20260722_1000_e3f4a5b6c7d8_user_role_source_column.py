"""§7.3 — user_roles.source column for scoped ERP360 role rewrites

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-02-12 10:00:00.000000

Adds `source` (String(20), default 'ifpi_native') to `user_roles` so
inbound ERP360 `role_changed` webhooks can wipe-and-rebuild only the
ERP360-managed subset. IFPI-native grants (INSTRUCTOR, cohort
assignments, native admin) survive every webhook.

See ERP360_BOLT_ON_WORK_LIST.md §7.3 for context.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_roles")}
    if "source" not in cols:
        op.add_column(
            "user_roles",
            sa.Column(
                "source",
                sa.String(length=20),
                nullable=False,
                server_default="ifpi_native",
            ),
        )
        op.create_index(
            "ix_user_roles_source",
            "user_roles",
            ["source"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_roles")}
    if "source" in cols:
        indexes = {ix["name"] for ix in insp.get_indexes("user_roles")}
        if "ix_user_roles_source" in indexes:
            op.drop_index("ix_user_roles_source", table_name="user_roles")
        op.drop_column("user_roles", "source")
