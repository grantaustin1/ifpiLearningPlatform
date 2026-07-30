"""One-off marketplace purge (Iter 40).

1. Opts every organization OUT of the public marketplace except the real
   academy (`ifpi-main`). Test factories created 300+ faker orgs whose
   PUBLISHED courses polluted the public catalog.
2. Runs the nightly test-debris cleanup tick immediately (now also covers
   'Entitlement Test%' / 'Paid E2E%' courses and force-opts-out test orgs).

Run:  cd /app/backend && python scripts/purge_marketplace_debris.py
      DATABASE_URL=sqlite:////app/backend/snapshots/pre_uat_ifpi_lms.db \
        python scripts/purge_marketplace_debris.py   # also fix the UAT snapshot
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal
from models import Organization

REAL_ORG_SLUGS = {"ifpi-main"}  # uat-sandbox is already opted out


def main() -> None:
    with SessionLocal() as db:
        flipped = (db.query(Organization)
                   .filter(Organization.slug.notin_(REAL_ORG_SLUGS),
                           Organization.marketplace_opt_in.is_(True))
                   .update({"marketplace_opt_in": False}, synchronize_session=False))
        db.commit()
        print(f"opted {flipped} orgs out of the marketplace")

        from services.test_debris_cleanup import tick
        stats = tick(db)
        print(f"debris cleanup: {stats}")


if __name__ == "__main__":
    main()
