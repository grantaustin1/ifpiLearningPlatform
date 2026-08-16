"""One-shot data migration: SQLite → PostgreSQL (Neon).

Copies every table registered on Base.metadata, preserving primary keys,
then resets PG sequences and stamps alembic head.

Usage:
    cd /app/backend
    python scripts/migrate_to_postgres.py \
        --sqlite sqlite:////app/backend/ifpi_lms.db \
        --pg "postgresql://user:pass@host/db?sslmode=require"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import Boolean, DateTime, create_engine, inspect, select, text  # noqa: E402
from sqlalchemy.types import JSON  # noqa: E402

from core.database import Base  # noqa: E402
import models  # noqa: F401,E402  (registers all tables)


def _convert(col, v):
    if v is None:
        return None
    if isinstance(col.type, Boolean) and isinstance(v, int):
        return bool(v)
    if isinstance(col.type, DateTime) and isinstance(v, str):
        return datetime.fromisoformat(v.replace(" ", "T", 1))
    if isinstance(col.type, JSON) and isinstance(v, (str, bytes)):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", required=True)
    ap.add_argument("--pg", required=True)
    args = ap.parse_args()

    src = create_engine(args.sqlite)
    dst = create_engine(args.pg)

    print("Resetting PostgreSQL schema…")
    with dst.begin() as dc:
        dc.execute(text("DROP SCHEMA public CASCADE"))
        dc.execute(text("CREATE SCHEMA public"))

    print("Creating schema on PostgreSQL…")
    Base.metadata.create_all(bind=dst, checkfirst=True)

    src_tables = set(inspect(src).get_table_names())
    total_rows = skipped = 0
    seen_pks: dict[str, set] = {}
    with src.connect() as sc, dst.begin() as dc:
        for table in Base.metadata.sorted_tables:
            if table.name not in src_tables:
                print(f"  ~ {table.name}: not in source, skipped")
                continue
            pk_cols = list(table.primary_key.columns)
            order = [table.c[pk_cols[0].name]] if len(pk_cols) == 1 else []
            rows = sc.execute(
                select(*[table.c[c.name] for c in table.columns]).order_by(*order)
            ).fetchall()
            if not rows:
                print(f"  - {table.name}: 0 rows")
                seen_pks[table.name] = set()
                continue
            cols = list(table.columns)
            # (col_index, parent_table_name) pairs for FK orphan checks
            fk_checks = []
            for i, c in enumerate(cols):
                for fk in c.foreign_keys:
                    if fk.column.primary_key:
                        fk_checks.append((i, fk.column.table.name))
            pks: set = set()
            seen_pks[table.name] = pks
            single_pk_idx = (
                [i for i, c in enumerate(cols) if c.primary_key][0]
                if len(pk_cols) == 1 else None)
            payload = []
            for row in rows:
                orphan = None
                for i, parent in fk_checks:
                    v = row[i]
                    if v is None:
                        continue
                    parent_pks = pks if parent == table.name else seen_pks.get(parent)
                    if parent_pks is not None and v not in parent_pks:
                        orphan = (cols[i].name, parent, v)
                        break
                if orphan:
                    skipped += 1
                    print(f"    ! {table.name} row skipped — "
                          f"{orphan[0]}={orphan[2]} missing in {orphan[1]}")
                    continue
                payload.append({c.name: _convert(c, row[i])
                                for i, c in enumerate(cols)})
                if single_pk_idx is not None:
                    pks.add(row[single_pk_idx])
            for i in range(0, len(payload), 500):
                dc.execute(table.insert(), payload[i:i + 500])
            total_rows += len(payload)
            print(f"  + {table.name}: {len(payload)} rows")

        print("Resetting sequences…")
        for table in Base.metadata.sorted_tables:
            pk = [c for c in table.primary_key.columns]
            if len(pk) == 1 and pk[0].autoincrement is not False \
                    and pk[0].type.python_type is int:
                dc.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', "
                    f"'{pk[0].name}'), COALESCE((SELECT MAX({pk[0].name}) "
                    f"FROM {table.name}), 0) + 1, false)"))

    print(f"Done — {total_rows} rows migrated, {skipped} orphan rows skipped.")


if __name__ == "__main__":
    main()
