"""course display_order + organization theme_preset

Revision ID: c1f29b3e9d04
Revises: 9acf884483b9
Create Date: 2026-02-08 13:10:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1f29b3e9d04"
down_revision = "9acf884483b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("courses") as bop:
        bop.add_column(sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))
        bop.create_index("ix_courses_display_order", ["display_order"])
    with op.batch_alter_table("organizations") as bop:
        bop.add_column(sa.Column("theme_preset", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as bop:
        bop.drop_column("theme_preset")
    with op.batch_alter_table("courses") as bop:
        bop.drop_index("ix_courses_display_order")
        bop.drop_column("display_order")
