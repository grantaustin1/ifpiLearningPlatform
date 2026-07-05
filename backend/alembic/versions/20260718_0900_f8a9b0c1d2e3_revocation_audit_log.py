"""Iter 30 — revocation audit log.

New table `certificate_revocation_events` records every REVOKE /
UNREVOKE action on a certificate with the actor, timestamp, and
optional reason. Compliance teams can trace decisions per cert.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-07-04 05:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificate_revocation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("certificate_id", sa.Integer(),
                  sa.ForeignKey("certificates.id"), nullable=False, index=True),
        sa.Column("actor_user_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False),  # REVOKE | UNREVOKE
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade():
    op.drop_table("certificate_revocation_events")
