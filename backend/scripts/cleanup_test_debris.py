"""Iter 23 — Manual invocation of the nightly test-debris cleanup.

Usage:
    python backend/scripts/cleanup_test_debris.py             # apply (default)
    python backend/scripts/cleanup_test_debris.py --dry-run   # preview only

The scheduler already runs this daily at 03:00 UTC. Use this script
before a big demo, or when reviewing CI leakage.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "/app/backend")

from core.database import SessionLocal
from services.test_debris_cleanup import tick


def main() -> int:
    p = argparse.ArgumentParser(description="Purge test-debris rows from the DB.")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be deleted without committing.")
    args = p.parse_args()

    with SessionLocal() as db:
        stats = tick(db, dry_run=args.dry_run)

    prefix = "[DRY-RUN] Would delete" if args.dry_run else "Deleted"
    print(f"{prefix}:")
    for k, v in stats.items():
        print(f"  {k:>18}: {v}")
    print(f"  {'total':>18}: {sum(stats.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
