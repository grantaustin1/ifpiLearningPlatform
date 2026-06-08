"""cohorts on users+invitations + audit_logs table

Revision ID: f6b832c5a4e1
Revises: e5a721f43b18
Create Date: 2026-02-08 15:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6b832c5a4e1"
down_revision = "e5a721f43b18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as bop:
        bop.add_column(sa.Column("cohort", sa.String(100), nullable=True))
        bop.create_index("ix_users_cohort", ["cohort"])
    with op.batch_alter_table("invitations") as bop:
        bop.add_column(sa.Column("cohort", sa.String(100), nullable=True))
        bop.create_index("ix_invitations_cohort", ["cohort"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(80), nullable=False, index=True),
        sa.Column("target_type", sa.String(60), nullable=True),
        sa.Column("target_id", sa.String(80), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_audit_org_created", "audit_logs", ["organization_id", "created_at"])
    op.create_index("ix_audit_actor_created", "audit_logs", ["actor_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_actor_created", "audit_logs")
    op.drop_index("ix_audit_org_created", "audit_logs")
    op.drop_table("audit_logs")
    with op.batch_alter_table("invitations") as bop:
        bop.drop_index("ix_invitations_cohort")
        bop.drop_column("cohort")
    with op.batch_alter_table("users") as bop:
        bop.drop_index("ix_users_cohort")
        bop.drop_column("cohort")
