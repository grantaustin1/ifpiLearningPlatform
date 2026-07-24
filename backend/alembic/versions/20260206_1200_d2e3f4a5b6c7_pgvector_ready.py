"""Iter 34 (P2 option a) — pgvector-ready SourceChunk.embedding.

Enable the `vector` Postgres extension (idempotent) and swap
`source_chunks.embedding` from JSON to `vector(1536)` when running
against a Postgres dialect. Adds an HNSW cosine index for fast ANN.

On SQLite (dev/CI) this migration is a NO-OP — the JSON column stays
as-is, and the model-level `_embedding_column()` helper picks the
matching type at import time (see `models/ai.py`).

Trigger: set `USE_PGVECTOR=true` in the environment AND run alembic
against a Postgres URL. Fresh Postgres deployments will inherit
`vector(1536)` from the initial-schema head after collapsing history.

Rollback: dropping the vector type reverts to JSON; existing rows'
`embedding` bytes are cast back to a `text` representation of the
array (lossy, but acceptable — embeddings are regeneratable from the
`text` column via `services.embedding_service.ingest_document`).
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa

# ── Alembic revision identifiers ───────────────────────────────────────
revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def _is_postgres(bind) -> bool:
    return bind.dialect.name in ("postgresql", "postgres")


def _pgvector_available(bind) -> bool:
    """True if the `vector` extension can be created on this DB. We're
    conservative — if the CREATE EXTENSION fails (missing shared lib
    or permission), we degrade to a NO-OP rather than crash the boot."""
    if not _is_postgres(bind):
        return False
    try:
        bind.exec_driver_sql("SELECT 1 FROM pg_available_extensions "
                              "WHERE name = 'vector'")
        row = bind.exec_driver_sql(
            "SELECT count(*) FROM pg_available_extensions "
            "WHERE name = 'vector'"
        ).scalar()
        return bool(row)
    except Exception:  # noqa: BLE001
        return False


def upgrade() -> None:
    bind = op.get_bind()

    # 1) SQLite dev / non-Postgres — nothing to do. JSON column stays.
    if not _is_postgres(bind):
        return

    # 2) Postgres but pgvector unavailable — extension not installed on
    #    the cluster. Skip; operator can enable + re-run.
    if not _pgvector_available(bind):
        return

    # 3) Postgres + pgvector — enable extension, swap column type, add
    #    HNSW cosine index. Guarded by USE_PGVECTOR so operators can
    #    stage the migration in a maintenance window.
    if os.environ.get("USE_PGVECTOR", "").lower() not in ("1", "true", "yes"):
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Cast existing JSON embeddings (list[float]) → vector(1536).
    # NULL rows survive as NULL. This one-shot USING clause works
    # because pgvector 0.5+ accepts textual `[1,2,3,…]` arrays.
    op.execute("""
        ALTER TABLE source_chunks
        ALTER COLUMN embedding TYPE vector(1536)
        USING (embedding::text::vector)
    """)

    # HNSW index for fast approximate cosine search.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_source_chunks_embedding_hnsw
        ON source_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    if not _pgvector_available(bind):
        return

    op.execute("DROP INDEX IF EXISTS ix_source_chunks_embedding_hnsw")
    # Cast vector back to JSON text so no data is lost even if slightly
    # reformatted (application will regenerate embeddings on next
    # ingest anyway).
    op.execute("""
        ALTER TABLE source_chunks
        ALTER COLUMN embedding TYPE json
        USING (embedding::text::json)
    """)
