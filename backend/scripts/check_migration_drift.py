"""Migration drift gate -- fails CI when SQLAlchemy models have changed
without a corresponding Alembic migration.

Only catches structural drift (new/missing tables and columns), ignoring
historical noise like server_default tweaks, index renames, and nullable
changes that accumulate in long-running projects.

Usage:
    python backend/scripts/check_migration_drift.py

Exit codes:
    0 -- models and migrations are in sync (no structural drift)
    1 -- structural drift detected (new table/column without migration)
"""
from __future__ import annotations

import os
import sys
import tempfile

# Set DATABASE_URL BEFORE any backend imports so that core.config picks it up
_db_path = os.path.join(tempfile.gettempdir(), "ifpi_migration_drift_check.db")
if os.path.exists(_db_path):
    os.remove(_db_path)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import produce_migrations
from alembic.operations.ops import (
    CreateTableOp,
    DropTableOp,
    AddColumnOp,
    DropColumnOp,
)
from sqlalchemy import create_engine

from core.database import Base
import models  # noqa: F401


def _collect_structural_ops(ops_list):
    """Recursively collect CreateTable, DropTable, AddColumn, DropColumn ops."""
    structural = []
    for op in ops_list:
        if isinstance(op, (CreateTableOp, DropTableOp, AddColumnOp, DropColumnOp)):
            structural.append(op)
        # Some ops have nested ops (e.g. batch alter)
        if hasattr(op, "ops"):
            structural.extend(_collect_structural_ops(op.ops))
    return structural


def check_drift() -> int:
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = Config(alembic_ini)

    engine = create_engine(os.environ["DATABASE_URL"])

    # 1. Bring temp DB to latest migration
    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        from alembic import command
        command.upgrade(alembic_cfg, "head")

    # 2. Autogenerate compare
    with engine.connect() as connection:
        mc = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": False,  # ignore default tweaks
                "target_metadata": Base.metadata,
                "render_as_batch": True,
            },
        )
        migrations = produce_migrations(mc, Base.metadata)

    upgrade_ops = migrations.upgrade_ops
    structural = _collect_structural_ops(upgrade_ops.ops)

    engine.dispose()  # close connection pool so SQLite file can be deleted on Windows
    if not structural:
        print("[OK] Models and migrations are structurally in sync -- no drift detected.")
        if os.path.exists(_db_path):
            os.remove(_db_path)
        return 0

    print("[FAIL] Structural migration drift detected -- models have changed but no migration covers them.")
    print()
    print("Missing operations:")
    print("-" * 60)
    for op in structural:
        if isinstance(op, CreateTableOp):
            print(f"  + CREATE TABLE {op.table_name}")
        elif isinstance(op, DropTableOp):
            print(f"  - DROP TABLE {op.table_name}")
        elif isinstance(op, AddColumnOp):
            print(f"  + ALTER TABLE {op.table_name} ADD COLUMN {op.column.name}")
        elif isinstance(op, DropColumnOp):
            print(f"  - ALTER TABLE {op.table_name} DROP COLUMN {op.column_name}")
    print("-" * 60)
    print()
    print("Fix: run `alembic revision --autogenerate -m \"describe your change\"`")
    print("     review the generated migration, then commit it.")

    engine.dispose()
    if os.path.exists(_db_path):
        os.remove(_db_path)
    return 1


if __name__ == "__main__":
    sys.exit(check_drift())
