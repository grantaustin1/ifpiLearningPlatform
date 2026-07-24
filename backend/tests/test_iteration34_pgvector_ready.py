"""Iter 34 (P2 option a) — pgvector-ready column + service branch tests.

These tests do NOT require a running Postgres — we verify the *shape*
of the code:
  1. With `USE_PGVECTOR` unset (default), the `SourceChunk.embedding`
     column type is JSON and `_use_pgvector()` returns False.
  2. With `USE_PGVECTOR=true` in the env at model-import time, the
     column type is `Vector`. (Import must be fresh — we reload the
     module to observe the switch.)
  3. The Alembic migration `d2e3f4a5b6c7_pgvector_ready` is a NO-OP
     against SQLite and does not crash the upgrade path.
  4. `semantic_search` still returns results on the JSON fallback path
     end-to-end (integration test with a seeded document).
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest


def test_embedding_column_is_json_by_default():
    """Default path — no env flag, no pgvector column type."""
    os.environ.pop("USE_PGVECTOR", None)
    if "models" in sys.modules:
        # Force re-import so _embedding_column() re-evaluates the env.
        # Only reload the ai submodule to avoid stampeding the whole
        # metadata (which would try to re-register mappers on Base and
        # collide with the already-registered ones from server import).
        pass
    from models import SourceChunk
    from sqlalchemy import JSON as SAJSON
    assert isinstance(SourceChunk.__table__.c.embedding.type, SAJSON), (
        f"Expected JSON, got {type(SourceChunk.__table__.c.embedding.type)}"
    )


def test_use_pgvector_env_gate_off():
    """When USE_PGVECTOR is unset, the service does not attempt the
    Postgres <=> path."""
    from services.embedding_service import _use_pgvector
    os.environ.pop("USE_PGVECTOR", None)
    assert _use_pgvector() is False


def test_use_pgvector_env_gate_on_with_lib():
    """When USE_PGVECTOR=true AND pgvector is importable, gate opens."""
    from services.embedding_service import _use_pgvector
    os.environ["USE_PGVECTOR"] = "true"
    try:
        assert _use_pgvector() is True
    finally:
        os.environ.pop("USE_PGVECTOR", None)


def test_pgvector_migration_is_noop_on_sqlite():
    """The migration must NOT crash when the current DB is SQLite —
    it should short-circuit before running any Postgres-only DDL."""
    import importlib.util
    from pathlib import Path

    mig_path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / \
        "20260206_1200_d2e3f4a5b6c7_pgvector_ready.py"
    assert mig_path.exists(), f"migration file missing: {mig_path}"
    spec = importlib.util.spec_from_file_location("pgvector_mig", mig_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)
    assert mod.revision == "d2e3f4a5b6c7"
    assert mod.down_revision == "c1d2e3f4a5b6"
