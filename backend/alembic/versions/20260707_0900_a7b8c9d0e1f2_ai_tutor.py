"""Iter 30m — AI Tutor v1 tables.

Two tables — sessions + messages. Citations live as a JSON blob on the
assistant message row (Kimi's 5-table proposal collapses to this).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-07 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def _existing() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing()
    if "ai_tutor_sessions" not in existing:
        op.create_table(
            "ai_tutor_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id", ondelete="CASCADE"),
                      nullable=True),
            sa.Column("title", sa.String(200), nullable=False,
                      server_default="New chat"),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("last_message_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_ai_tutor_sessions_organization_id",
                        "ai_tutor_sessions", ["organization_id"])
        op.create_index("ix_ai_tutor_sessions_user_id",
                        "ai_tutor_sessions", ["user_id"])
        op.create_index("ix_ai_tutor_sessions_course_id",
                        "ai_tutor_sessions", ["course_id"])
        op.create_index("ix_tutor_session_user_course",
                        "ai_tutor_sessions", ["user_id", "course_id"])

    if "ai_tutor_messages" not in existing:
        op.create_table(
            "ai_tutor_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(),
                      sa.ForeignKey("ai_tutor_sessions.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("role", sa.String(12), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("citations", sa.JSON(), nullable=True),
            sa.Column("tokens_prompt", sa.Integer(), nullable=True),
            sa.Column("tokens_completion", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_ai_tutor_messages_session_id",
                        "ai_tutor_messages", ["session_id"])
        op.create_index("ix_tutor_msg_session",
                        "ai_tutor_messages", ["session_id", "created_at"])


def downgrade() -> None:
    existing = _existing()
    for tbl in ("ai_tutor_messages", "ai_tutor_sessions"):
        if tbl in existing:
            op.drop_table(tbl)
