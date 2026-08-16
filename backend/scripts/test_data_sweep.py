"""One-off production test-data sweep (June 2026, user-approved).

Deletes:
  1. All organizations except KEEP_ORG_IDS and everything inside them
     (users, courses, enrollments, certs, ...) via a recursive FK walk.
  2. Pattern-matched test accounts inside the keep orgs.
  3. UAT-account debris: certificates, enrollments, slide/course views,
     notifications and badges (the accounts themselves stay).

Usage:
    python scripts/test_data_sweep.py --dry-run   # rollback at end
    python scripts/test_data_sweep.py --execute   # commit
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import engine  # noqa: E402

KEEP_ORG_IDS = (1, 327)
KEEP_EMAILS = (
    "admin@ifpi.org", "learner@ifpi.org", "grant@edgefitness.co.za",
    "qa-admin@ifpi.org", "uat-admin@ifpi.org", "uat-learner@ifpi.org",
    "migration@ifpi-org-1.local", "migration@ifpi-org-327.local",
    "templates@system.local",
)
TEST_EMAIL_PATTERNS = [
    "iter33-%", "iter33fe-%", "rl-%", "scoped-test-%", "shape-test-%",
    "jit-test-%", "formpost-%", "returnto-%", "openredirect-%",
    "jsonpath-%", "outbox-admin-%", "gate-on-%", "legacy-env-%",
    "link-claim-%", "link-both-%", "link-native-%", "foreigner-%",
    "foreign-admin-%", "verified-%", "unverified-%", "noslug-%",
    "live-smoke-%", "change-pw-%", "reset-test-%", "verify-test-%",
    "deleted-%@anon.invalid", "%@example.com", "%@example.net",
    "%@ifpi.test", "%@erp360.test", "%@x.test",
]
UAT_EMAILS = ("uat-admin@ifpi.org", "uat-learner@ifpi.org")
CHUNK = 5000


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    raw = engine.raw_connection()
    cur = raw.cursor()

    # ── FK graph: parent_table -> [(child_table, child_column)] ──────
    cur.execute("""
        SELECT ccu.table_name AS parent, tc.table_name AS child,
               kcu.column_name AS child_col
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
    """)
    children = defaultdict(list)
    for parent, child, col in cur.fetchall():
        children[parent].append((child, col))

    cur.execute("""
        SELECT table_name FROM information_schema.columns
        WHERE table_schema='public' AND column_name='id'
    """)
    has_id = {r[0] for r in cur.fetchall()}

    deleted: dict[str, set] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)

    def recursive_delete(table: str, ids: list):
        ids = [i for i in set(ids) if i not in deleted[table]]
        if not ids:
            return
        deleted[table].update(ids)  # mark early — breaks FK cycles
        for chunk_start in range(0, len(ids), CHUNK):
            chunk = ids[chunk_start:chunk_start + CHUNK]
            for child, col in children.get(table, []):
                if child in has_id:
                    cur.execute(
                        f'SELECT id FROM "{child}" WHERE "{col}" = ANY(%s)',
                        (chunk,))
                    child_ids = [r[0] for r in cur.fetchall()]
                    recursive_delete(child, child_ids)
                else:
                    cur.execute(
                        f'DELETE FROM "{child}" WHERE "{col}" = ANY(%s)',
                        (chunk,))
                    counts[child] += cur.rowcount
            cur.execute(f'DELETE FROM "{table}" WHERE id = ANY(%s)', (chunk,))
            counts[table] += cur.rowcount

    # ── 1. Doomed organizations ──────────────────────────────────────
    cur.execute("SELECT id FROM organizations WHERE id != ALL(%s)",
                (list(KEEP_ORG_IDS),))
    doomed_orgs = [r[0] for r in cur.fetchall()]
    print(f"Doomed organizations: {len(doomed_orgs)}")

    # ── 2. Test accounts inside keep orgs ────────────────────────────
    like = " OR ".join(["email LIKE %s"] * len(TEST_EMAIL_PATTERNS))
    cur.execute(
        f"SELECT id FROM users WHERE organization_id = ANY(%s) "
        f"AND email != ALL(%s) AND ({like})",
        [list(KEEP_ORG_IDS), list(KEEP_EMAILS)] + TEST_EMAIL_PATTERNS)
    doomed_users_keep_orgs = [r[0] for r in cur.fetchall()]
    print(f"Doomed test users inside keep orgs: {len(doomed_users_keep_orgs)}")

    # Safety: no keep-org course may be owned by a doomed user
    cur.execute(
        "SELECT id, title FROM courses WHERE organization_id = ANY(%s) "
        "AND created_by_id = ANY(%s)",
        (list(KEEP_ORG_IDS), doomed_users_keep_orgs or [0]))
    conflict = cur.fetchall()
    if conflict:
        print(f"ABORT — keep-org courses owned by doomed users: {conflict}")
        raw.rollback()
        return

    recursive_delete("users", doomed_users_keep_orgs)
    recursive_delete("organizations", doomed_orgs)

    # ── 3. UAT account debris (accounts stay) ────────────────────────
    cur.execute("SELECT id FROM users WHERE email = ANY(%s)",
                (list(UAT_EMAILS),))
    uat_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM certificates WHERE user_id = ANY(%s)",
                (uat_ids,))
    recursive_delete("certificates", [r[0] for r in cur.fetchall()])
    cur.execute("SELECT id FROM enrollments WHERE user_id = ANY(%s)",
                (uat_ids,))
    recursive_delete("enrollments", [r[0] for r in cur.fetchall()])
    for tbl in ("slide_views", "course_views", "notifications",
                "user_badges", "flashcard_reviews"):
        cur.execute(f'DELETE FROM "{tbl}" WHERE user_id = ANY(%s)', (uat_ids,))
        counts[tbl] += cur.rowcount
    cur.execute("UPDATE users SET xp = 0 WHERE id = ANY(%s) AND xp IS NOT NULL",
                (uat_ids,)) if _col_exists(cur, "users", "xp") else None

    # Any remaining certs pointing at deleted courses (defensive)
    cur.execute("SELECT id FROM certificates WHERE course_id IS NULL "
                "AND live_session_id IS NULL")
    recursive_delete("certificates", [r[0] for r in cur.fetchall()])

    print("\nRows deleted per table:")
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n:
            print(f"  {t}: {n}")
    print(f"TOTAL: {sum(counts.values())}")

    if args.execute:
        raw.commit()
        print("\nCOMMITTED.")
    else:
        raw.rollback()
        print("\nDRY RUN — rolled back.")
    raw.close()


def _col_exists(cur, table, col):
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name=%s "
        "AND column_name=%s", (table, col))
    return cur.fetchone() is not None


if __name__ == "__main__":
    main()
