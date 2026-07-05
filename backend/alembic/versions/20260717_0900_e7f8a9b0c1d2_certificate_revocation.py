"""Iter 29 — certificate revocation.

Adds:
- `certificates.revoked_at` — set by admin action; nullable, indexed.
- `certificates.revoked_reason` — optional short reason string.

Revoked certs are still fetch-able but the public verify / share
endpoints show a "REVOKED" state and the OG image renders a red
"REVOKED" ribbon overlay so LinkedIn/Twitter refresh their previews on
next crawl.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-04 04:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("certificates") as b:
        b.add_column(sa.Column("revoked_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("revoked_reason", sa.String(255), nullable=True))
        b.create_index("ix_certificates_revoked_at", ["revoked_at"])


def downgrade():
    with op.batch_alter_table("certificates") as b:
        b.drop_index("ix_certificates_revoked_at")
        b.drop_column("revoked_reason")
        b.drop_column("revoked_at")
