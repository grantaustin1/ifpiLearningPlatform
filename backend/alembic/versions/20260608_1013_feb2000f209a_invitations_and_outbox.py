"""invitations_and_outbox

Revision ID: feb2000f209a
Revises: 9e33790c5d6e
Create Date: 2026-06-08 10:13:42.879496

Creates the `invitations` and `outbox_messages` tables. The original
auto-generated stub was empty (a `pass`), which only worked on local dev
because `Base.metadata.create_all()` was running at startup and silently
creating the tables behind alembic's back. On a clean CI checkout
(alembic-only schema build), the NEXT migration tried to ALTER
`outbox_messages` and failed with "no such table".

Made idempotent so dev DBs that already have these tables (via
create_all) can still alembic-upgrade cleanly.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "feb2000f209a"
down_revision: Union[str, None] = "9e33790c5d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(insp, table: str) -> bool:
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has(insp, "invitations"):
        op.create_table(
            "invitations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("email", sa.String(200), nullable=False),
            sa.Column("name", sa.String(200)),
            sa.Column("role", sa.String(50), nullable=False),
            # `cohort` is added by the later cohorts_audit migration (f6b832c5a4e1)
            sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("invited_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_invites_org_email", "invitations",
                        ["organization_id", "email"])

    if not _has(insp, "outbox_messages"):
        # Note: `attempt_count` + `next_attempt_at` are added by the next
        # migration (`comments_and_retry`). Don't include them here — that
        # migration's ALTER expects them missing on a fresh chain.
        op.create_table(
            "outbox_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("to_email", sa.String(200), nullable=False),
            sa.Column("to_name", sa.String(200)),
            sa.Column("subject", sa.String(300), nullable=False),
            sa.Column("body_text", sa.Text()),
            sa.Column("body_html", sa.Text()),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("template", sa.String(60)),
            sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED",
                      index=True),
            sa.Column("transport", sa.String(20)),
            sa.Column("transport_message_id", sa.String(120)),
            sa.Column("error", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_outbox_status_created", "outbox_messages",
                        ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("outbox_messages")
    op.drop_table("invitations")
