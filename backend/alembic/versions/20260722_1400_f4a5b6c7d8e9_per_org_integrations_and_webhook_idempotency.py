"""§7.4 + §6.4 — Per-org integrations JSONB + SQL-backed webhook idempotency

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-02-12 14:00:00.000000

Two integration-hardening additions:

1. `organizations.integrations` JSON column (default `{}`). Holds
   per-org ERP360 connection state — replaces the global `SSO_ENABLED`
   env flag as the source of truth for WHICH orgs participate in the
   ERP360 bolt-on. See ERP360_BOLT_ON_WORK_LIST §7.4.

2. `erp360_seen_events` table for replica-safe idempotency on inbound
   webhook `X-ERP360-Event-Id`. Replaces the in-memory
   `_SEEN_EVENT_IDS` dict so dedup survives restart and scale-out.
   Mirrors the shape of the pre-existing `sso_jti_seen` table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # ── 1. organizations.integrations ────────────────────────────────
    org_cols = {c["name"] for c in insp.get_columns("organizations")}
    if "integrations" not in org_cols:
        op.add_column(
            "organizations",
            sa.Column(
                "integrations",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            ),
        )

    # ── 2. erp360_seen_events ────────────────────────────────────────
    if "erp360_seen_events" not in insp.get_table_names():
        op.create_table(
            "erp360_seen_events",
            sa.Column("event_id", sa.String(length=120), primary_key=True),
            sa.Column("received_at", sa.DateTime(),
                      nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            "ix_erp360_seen_events_at",
            "erp360_seen_events",
            ["received_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "erp360_seen_events" in insp.get_table_names():
        indexes = {ix["name"] for ix in insp.get_indexes("erp360_seen_events")}
        if "ix_erp360_seen_events_at" in indexes:
            op.drop_index("ix_erp360_seen_events_at",
                          table_name="erp360_seen_events")
        op.drop_table("erp360_seen_events")

    org_cols = {c["name"] for c in insp.get_columns("organizations")}
    if "integrations" in org_cols:
        op.drop_column("organizations", "integrations")
