"""Full logical backup of the Neon DB — every table to CSV, tarred.

Usage: python scripts/db_backup.py
Output: /app/backend/backups/neon_backup_<utc-ts>.tar.gz
"""
from __future__ import annotations

import csv
import io
import os
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import engine  # noqa: E402
from sqlalchemy import text  # noqa: E402


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path("/app/backend/backups")
    out_dir.mkdir(exist_ok=True)
    tar_path = out_dir / f"neon_backup_{ts}.tar.gz"

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1")
        tables = [r[0] for r in cur.fetchall()]
        total_rows = 0
        with tarfile.open(tar_path, "w:gz") as tar:
            for t in tables:
                buf = io.StringIO()
                cur.copy_expert(
                    f'COPY "{t}" TO STDOUT WITH (FORMAT csv, HEADER)', buf)
                data = buf.getvalue().encode()
                n = max(0, data.count(b"\n") - 1)
                total_rows += n
                info = tarfile.TarInfo(name=f"{t}.csv")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                print(f"  {t}: {n} rows")
        print(f"\nBackup complete: {tar_path} "
              f"({tar_path.stat().st_size / 1e6:.1f} MB, {total_rows} rows, "
              f"{len(tables)} tables)")
    finally:
        raw.close()


if __name__ == "__main__":
    main()
