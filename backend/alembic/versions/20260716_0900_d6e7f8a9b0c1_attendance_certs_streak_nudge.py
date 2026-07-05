"""Iter 27 — attendance certificates + streak nudge tracking.

Adds:
- `certificates.live_session_id` — nullable FK for attendance certs
- `users.streak_nudge_last_sent_at` — dedup nudge emails

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-04 03:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("certificates") as b:
        b.add_column(sa.Column("live_session_id", sa.Integer(), nullable=True))
        b.create_index("ix_certificates_live_session_id",
                       ["live_session_id"])
        b.create_foreign_key(
            "fk_certificates_live_session_id",
            "live_sessions", ["live_session_id"], ["id"],
        )
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column(
            "streak_nudge_last_sent_at", sa.DateTime(), nullable=True,
        ))


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("streak_nudge_last_sent_at")
    with op.batch_alter_table("certificates") as b:
        b.drop_constraint("fk_certificates_live_session_id",
                          type_="foreignkey")
        b.drop_index("ix_certificates_live_session_id")
        b.drop_column("live_session_id")
