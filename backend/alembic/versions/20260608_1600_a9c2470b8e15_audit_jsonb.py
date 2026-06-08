"""audit_metadata: JSON -> JSONB on Postgres (no-op on SQLite)

Revision ID: a9c2470b8e15
Revises: f6b832c5a4e1
Create Date: 2026-02-08 16:00:00

SQLAlchemy's `sa.JSON()` maps to:
  - SQLite: TEXT  (json stored as a string)
  - Postgres: JSON  (a queryable but un-indexable JSON type)
We want Postgres to use JSONB instead so we can build GIN indexes on
`audit_logs.audit_metadata` and run efficient `?`/`@>` queries.

On SQLite this migration is a no-op — there is no JSONB; the existing TEXT
column already accepts arbitrary JSON.
"""
from __future__ import annotations

from alembic import op

revision = "a9c2470b8e15"
down_revision = "f6b832c5a4e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Convert column type to JSONB (lossless — existing JSON values cast cleanly)
    op.execute(
        "ALTER TABLE audit_logs "
        "ALTER COLUMN audit_metadata TYPE JSONB "
        "USING audit_metadata::jsonb"
    )
    # GIN index for fast contains/key-existence lookups
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_metadata_gin "
        "ON audit_logs USING GIN (audit_metadata)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_audit_metadata_gin")
    op.execute(
        "ALTER TABLE audit_logs "
        "ALTER COLUMN audit_metadata TYPE JSON "
        "USING audit_metadata::json"
    )
