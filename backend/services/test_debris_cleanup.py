"""Iter 23 — Nightly test-debris cleanup.

Purges leftover test data accumulated across CI runs so the DB stays
lean. Runs nightly at 03:00 UTC via APScheduler (see outbox_worker).

What we remove (all filtered by *pattern*, never by timestamp — a
pattern-safe approach is more resilient to clock skew across CI runs):

Courses (title patterns):
    - `TEST_%`         iter17/iter30 direct-DB seeds
    - `UITEST_%`       iter30 UI tests
    - `Iter% AutoComplete%`   iter21 completion tests
    - `iter%test%`     misc iter test residue
    - `%_prereq_%`     iter30 prereq harness
    Along with each course we cascade-delete slides, enrollments, quiz
    attempts and progress rows so no orphans remain.

Live sessions (title patterns):
    - `UITEST-%`, `iter22-%`, `iter23-%`
    Along with their RSVPs.

Terms versions (version patterns):
    - `iter%`, `TEST-%`, `%audit%`
    Along with their acceptances. Never removes rows with is_current=1
    (safety guard — someone might be using them).

Outbox messages (template patterns):
    - Older than 30 days AND `%test%` in template or subject
    (Keeps recent history for debugging, purges old test churn.)

The cleanup is idempotent and lock-free — the worker holds no locks
between deletions, so a concurrent request touching a row will get
whichever version it looks up first (SQLAlchemy's default MVCC).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from models import (
    Course, CourseView, LiveSession, LiveSessionRsvp, OutboxMessage,
    TermsAcceptance, TermsVersion,
)

logger = logging.getLogger(__name__)


# ── Regex + LIKE patterns ────────────────────────────────────────────
COURSE_TITLE_PATTERNS = [
    "TEST_%",              # TEST_Paid_..., TEST_prereq_... (underscore is a wildcard, matches TEST-*, TEST_*, TESTx*)
    "UITEST%",             # UITEST-, UITEST_ variants
    "Iter% AutoComplete%",   # iter21 auto-complete residue
    "Iter% SCORM %",         # iter18 SCORM smoke courses
    "iter%test%",
    "%prereq%",            # any prereq-flavoured test residue
    "iter21%",             # any iter21-prefixed test title
    "iter30%",             # any iter30-prefixed test title
    "Iter30%",             # capitalised iter30 tests
    # ── Iter 24 additions ────────────────────────────────────────────
    "iter22-%",            # marketplace tests
    "iter23-%",            # recurrence + reminder tests
    "iter24-%",            # funnel + EXDATE + subscription tests
    "Iter22 test%",        # live_sessions iter22 fixture titles
    "SmokeTest%",          # generic smoke-test prefix
    "%SCORM smoke%",       # SCORM smoke residue
    "%_debris_%",          # cleanup-tests' own debris fixtures
    "AI Test %",           # ai_authoring test residue
    "Bulk Import Test%",   # bulk-import test residue
    "Learning Path Test%",  # learning-path test residue
<<<<<<< HEAD
    # ── Iter 40 additions (marketplace debris) ───────────────────────
    "Entitlement Test%",   # iter39 entitlement harness residue
    "Paid E2E%",           # iter39 Stripe E2E residue
    "Stripe Test%",        # iter39 Stripe checkout harness residue
    "Stripe Frontend E2E%",  # iter39 Stripe browser-flow residue
    "Ent Inspect%",        # entitlements-inspector harness residue
]

# Org slugs created by test factories/harnesses. These orgs must never
# surface in the cross-tenant public marketplace — the nightly pass
# force-opts them out (their PUBLISHED faker courses otherwise pollute
# the public catalog). Real academies never match these prefixes.
TEST_ORG_SLUG_PATTERNS = [
    "factory-org-%",
    "test-acad-%",
    "outbox-%",
    "other-acad-%",
    "ent-other-%",
    "ui-acad-%",
=======
>>>>>>> origin/main
]

LIVE_SESSION_TITLE_PATTERNS = [
    "UITEST-%",
    "iter22-%",
    "iter23-%",
    "iter24-%",              # Iter 24 additions
    "Iter22 test%",
    "iter24-exdate-%",
    "iter24-cancelled-%",
    "iter24-cleanup-%",
    "SmokeTest%",
]

TERMS_VERSION_PATTERNS = [
    "iter%",
    "TEST-%",
    "%audit%",
    "iter30l-%",           # Iter 24 — explicit iter30l cleanup pattern
]


def _delete_stale_courses(db: Session) -> int:
    """Purge test-seeded courses + all their dependent rows.

    We temporarily disable SQLite FK enforcement, walk every table with
    a `course_id` column and DELETE its rows for the target courses,
    then re-enable FK enforcement. This is safe because a stale test
    course has no legitimate cross-refs — any FK to it is itself test
    debris and MUST be cleared. If FK integrity is compromised after
    this pass, the whole DB was already inconsistent."""
    course_ids: set[int] = set()
    for pat in COURSE_TITLE_PATTERNS:
        rows = db.query(Course.id).filter(Course.title.like(pat)).all()
        for (cid,) in rows:
            course_ids.add(cid)
    if not course_ids:
        return 0

    id_csv = ",".join(str(i) for i in course_ids)
    bind = db.get_bind()
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(bind)

    # SQLite-specific: disable FK enforcement for the duration of the pass.
    is_sqlite = bind.dialect.name == "sqlite"
    if is_sqlite:
        db.execute(text("PRAGMA foreign_keys = OFF"))

    try:
        # Two passes: first any table that has BOTH `course_id` and a
        # discoverable child of its own, then the primary tables. But
        # since FK is off, order doesn't matter. Single pass suffices.
        for tbl in insp.get_table_names():
            if tbl == "courses":
                continue
            cols = [c["name"] for c in insp.get_columns(tbl)]
            if "course_id" not in cols:
                continue
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE course_id IN ({id_csv})"))
            except Exception as e:
                logger.warning("Skipping %s: %s", tbl, e)
        # Also clear tables with a `prerequisite_course_id`
        for tbl in insp.get_table_names():
            if tbl == "courses":
                continue
            cols = [c["name"] for c in insp.get_columns(tbl)]
            if "prerequisite_course_id" in cols:
                try:
                    db.execute(text(
                        f"DELETE FROM {tbl} WHERE prerequisite_course_id IN ({id_csv})"
                    ))
                except Exception as e:
                    logger.warning("Skipping %s (prereq): %s", tbl, e)
        n = db.query(Course).filter(Course.id.in_(list(course_ids))).delete(
            synchronize_session=False)
    finally:
        if is_sqlite:
            db.execute(text("PRAGMA foreign_keys = ON"))
    return n


def _delete_stale_live_sessions(db: Session) -> int:
    ids: set[int] = set()
    for pat in LIVE_SESSION_TITLE_PATTERNS:
        rows = db.query(LiveSession.id).filter(LiveSession.title.like(pat)).all()
        for (sid,) in rows:
            ids.add(sid)
    if not ids:
        return 0
    id_list = list(ids)
    db.query(LiveSessionRsvp).filter(
        LiveSessionRsvp.session_id.in_(id_list)
    ).delete(synchronize_session=False)
    n = db.query(LiveSession).filter(
        LiveSession.id.in_(id_list)
    ).delete(synchronize_session=False)
    return n


def _delete_stale_terms_versions(db: Session) -> int:
    """Purge non-current test terms versions + their acceptances."""
    # Never touch is_current=True rows — someone might still be using them
    version_ids: set[int] = set()
    for pat in TERMS_VERSION_PATTERNS:
        rows = db.query(TermsVersion.id).filter(
            TermsVersion.version.like(pat),
            TermsVersion.is_current.is_(False),
        ).all()
        for (vid,) in rows:
            version_ids.add(vid)
    if not version_ids:
        return 0
    id_list = list(version_ids)
    db.query(TermsAcceptance).filter(
        TermsAcceptance.terms_version_id.in_(id_list)
    ).delete(synchronize_session=False)
    n = db.query(TermsVersion).filter(
        TermsVersion.id.in_(id_list)
    ).delete(synchronize_session=False)
    return n


def _delete_stale_outbox(db: Session) -> int:
    """Purge outbox messages that are older than 30 days AND look like
    they came from a test run. Recent messages are always kept for
    debugging."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    n = db.query(OutboxMessage).filter(
        OutboxMessage.created_at < cutoff,
        or_(
            OutboxMessage.template.like("%test%"),
            OutboxMessage.subject.like("%test%"),
            OutboxMessage.subject.like("%TEST%"),
        ),
    ).delete(synchronize_session=False)
    return n


def _delete_stale_course_views(db: Session) -> int:
    """Iter 24 — CourseView rows referencing already-deleted courses
    become orphans (FK is nullable? no — it's NOT NULL). But CASCADE
    already handles them via the courses cleanup. This function only
    purges *old* views (>90 days) to keep the funnel table lean; funnel
    analytics never look back that far anyway."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    n = db.query(CourseView).filter(
        CourseView.viewed_on_date < cutoff
    ).delete(synchronize_session=False)
    return n


<<<<<<< HEAD
def _optout_test_orgs_from_marketplace(db: Session) -> int:
    """Force marketplace_opt_in=False on orgs whose slug matches a test
    factory pattern. Returns rows flipped."""
    from models import Organization
    flipped = 0
    for pat in TEST_ORG_SLUG_PATTERNS:
        flipped += (db.query(Organization)
                    .filter(Organization.slug.like(pat),
                            Organization.marketplace_opt_in.is_(True))
                    .update({"marketplace_opt_in": False},
                            synchronize_session=False))
    return flipped


=======
>>>>>>> origin/main
def tick(db: Session, dry_run: bool = False) -> dict:
    """Run the full cleanup pass. Returns a dict of {resource: rows_deleted}.

    If `dry_run=True`, rollback instead of committing (useful for smoke
    testing the counts without mutating state)."""
    stats = {
        "courses": _delete_stale_courses(db),
        "live_sessions": _delete_stale_live_sessions(db),
        "terms_versions": _delete_stale_terms_versions(db),
        "outbox_messages": _delete_stale_outbox(db),
        "course_views": _delete_stale_course_views(db),
<<<<<<< HEAD
        "marketplace_optouts": _optout_test_orgs_from_marketplace(db),
=======
>>>>>>> origin/main
    }
    if dry_run:
        db.rollback()
    else:
        db.commit()
    total = sum(stats.values())
    if total:
        logger.info(
            "Nightly test-debris cleanup: %s (total=%s)", stats, total
        )
    return stats
