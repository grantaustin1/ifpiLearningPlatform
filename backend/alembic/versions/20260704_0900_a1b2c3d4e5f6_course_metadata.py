"""Course.metadata_json for mind-map layout persistence (Iter 28).

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-07-04 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "courses" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("courses")}
        if "metadata_json" not in cols:
            with op.batch_alter_table("courses") as bop:
                bop.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("courses") as bop:
        bop.drop_column("metadata_json")
