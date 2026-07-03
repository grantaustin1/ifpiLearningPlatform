"""Iter 22 — Live Sessions module.

Adds two tables:
- `live_sessions`: one row per scheduled cohort meeting (BYO join URL).
- `live_session_rsvps`: RSVPs and attendance tracking per learner.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _tables()
    if "live_sessions" not in existing:
        op.create_table(
            "live_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("meeting_url", sa.String(1000), nullable=False),
            sa.Column("start_at", sa.DateTime(), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False,
                      server_default="60"),
            sa.Column("host_name", sa.String(200), nullable=True),
            sa.Column("cohort", sa.String(100), nullable=True),
            sa.Column("max_attendees", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_live_sessions_organization_id", "live_sessions",
                        ["organization_id"])
        op.create_index("ix_live_sessions_course_id", "live_sessions",
                        ["course_id"])
        op.create_index("ix_live_sessions_start_at", "live_sessions", ["start_at"])
        op.create_index("ix_live_sessions_cohort", "live_sessions", ["cohort"])
        op.create_index("ix_live_sessions_org_start", "live_sessions",
                        ["organization_id", "start_at"])

    if "live_session_rsvps" not in existing:
        op.create_table(
            "live_session_rsvps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(),
                      sa.ForeignKey("live_sessions.id"), nullable=False),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="RSVP"),
            sa.Column("rsvped_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("attendance_marked_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("session_id", "user_id",
                                name="uq_rsvp_session_user"),
        )
        op.create_index("ix_live_session_rsvps_session_id",
                        "live_session_rsvps", ["session_id"])
        op.create_index("ix_live_session_rsvps_user_id",
                        "live_session_rsvps", ["user_id"])
        op.create_index("ix_live_session_rsvps_status",
                        "live_session_rsvps", ["status"])


def downgrade() -> None:
    existing = _tables()
    if "live_session_rsvps" in existing:
        op.drop_table("live_session_rsvps")
    if "live_sessions" in existing:
        op.drop_table("live_sessions")
