"""Iter 23 — Test-debris cleanup service tests.

Covers:
- Creating debris rows (matching TEST_%, iter22-%, iter30l-% patterns)
  and verifying the cleanup service removes them.
- Idempotency: a second pass on a clean DB returns all zeros.
- Dry-run mode: reports counts but rolls back (no rows actually deleted).
- Safety: rows that don't match test patterns are preserved.
- Terms guardrail: is_current=True terms versions are NEVER deleted
  even if their `version` matches a purge pattern.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/backend")

import pytest

from core.database import SessionLocal
from models import (
    Course, CourseStatus, LiveSession, LiveSessionRsvp, OutboxMessage,
    Organization, TermsAcceptance, TermsVersion, User,
)
from services.test_debris_cleanup import tick


@pytest.fixture()
def sample_debris():
    """Seed one of each kind of debris row + one legit row. Yield the
    ids so we can inspect state after the cleanup, and clean up
    explicitly at teardown so the test itself doesn't leave residue."""
    seeded = {}
    with SessionLocal() as db:
        org = db.query(Organization).first()
        user = db.query(User).first()

        debris_course = Course(
            organization_id=org.id, title="TEST_debris_iter23_smoke",
            cover_color="from-red-500 to-red-700",
            status=CourseStatus.DRAFT, price_cents=0, currency="USD",
        )
        legit_course = Course(
            organization_id=org.id, title="Legit Course DO NOT DELETE Iter23",
            cover_color="from-blue-500 to-blue-700",
            status=CourseStatus.PUBLISHED, price_cents=0, currency="USD",
        )

        debris_session = LiveSession(
            organization_id=org.id, title="iter22-cleanup-test-debris",
            meeting_url="https://zoom.us/j/999999",
            start_at=datetime.now(timezone.utc) + timedelta(days=90),
            duration_minutes=30, created_by_id=user.id,
        )
        legit_session = LiveSession(
            organization_id=org.id, title="Real cohort call Q4",
            meeting_url="https://zoom.us/j/888888",
            start_at=datetime.now(timezone.utc) + timedelta(days=91),
            duration_minutes=30, created_by_id=user.id,
        )

        debris_terms = TermsVersion(
            organization_id=org.id, version="iter30l-cleanup-test",
            title="Debris", body_markdown="debris",
            is_current=False, published_by_user_id=user.id,
            published_at=datetime.now(timezone.utc),
        )
        # Terms version that MATCHES the pattern but is CURRENT — must be preserved
        protected_terms = TermsVersion(
            organization_id=org.id, version="iter30l-protected-current",
            title="Protected", body_markdown="alive",
            is_current=True, published_by_user_id=user.id,
            published_at=datetime.now(timezone.utc),
        )

        db.add_all([debris_course, legit_course, debris_session,
                    legit_session, debris_terms, protected_terms])
        db.commit()

        seeded = {
            "debris_course_id": debris_course.id,
            "legit_course_id": legit_course.id,
            "debris_session_id": debris_session.id,
            "legit_session_id": legit_session.id,
            "debris_terms_id": debris_terms.id,
            "protected_terms_id": protected_terms.id,
        }

    yield seeded

    # Cleanup: force-remove anything left (protected_terms is the main risk)
    with SessionLocal() as db:
        db.query(Course).filter(
            Course.id.in_([seeded["debris_course_id"], seeded["legit_course_id"]])
        ).delete(synchronize_session=False)
        db.query(LiveSessionRsvp).filter(
            LiveSessionRsvp.session_id.in_(
                [seeded["debris_session_id"], seeded["legit_session_id"]])
        ).delete(synchronize_session=False)
        db.query(LiveSession).filter(
            LiveSession.id.in_(
                [seeded["debris_session_id"], seeded["legit_session_id"]])
        ).delete(synchronize_session=False)
        # Protected terms — must delete because we made it is_current=True
        # (blocks other tests otherwise)
        db.query(TermsAcceptance).filter(
            TermsAcceptance.terms_version_id.in_(
                [seeded["debris_terms_id"], seeded["protected_terms_id"]])
        ).delete(synchronize_session=False)
        db.query(TermsVersion).filter(
            TermsVersion.id.in_(
                [seeded["debris_terms_id"], seeded["protected_terms_id"]])
        ).delete(synchronize_session=False)
        db.commit()


def test_cleanup_removes_debris_courses(sample_debris):
    with SessionLocal() as db:
        stats = tick(db)
    with SessionLocal() as db:
        # Debris removed
        assert db.get(Course, sample_debris["debris_course_id"]) is None
        # Legit preserved
        assert db.get(Course, sample_debris["legit_course_id"]) is not None
    assert stats["courses"] >= 1


def test_cleanup_removes_debris_live_sessions(sample_debris):
    with SessionLocal() as db:
        stats = tick(db)
    with SessionLocal() as db:
        assert db.get(LiveSession, sample_debris["debris_session_id"]) is None
        assert db.get(LiveSession, sample_debris["legit_session_id"]) is not None
    assert stats["live_sessions"] >= 1


def test_cleanup_preserves_current_terms_versions(sample_debris):
    """Even if a `version` matches an iter% pattern, is_current=True rows
    must never be removed — they might still be gating live traffic."""
    with SessionLocal() as db:
        tick(db)
    with SessionLocal() as db:
        # Debris removed
        assert db.get(TermsVersion, sample_debris["debris_terms_id"]) is None
        # Protected (is_current=True) preserved
        assert db.get(TermsVersion, sample_debris["protected_terms_id"]) is not None


def test_cleanup_dry_run_makes_no_changes(sample_debris):
    """Dry-run reports counts but MUST NOT commit any DELETEs."""
    with SessionLocal() as db:
        stats = tick(db, dry_run=True)
    # Debris rows should still exist
    with SessionLocal() as db:
        assert db.get(Course, sample_debris["debris_course_id"]) is not None
        assert db.get(LiveSession, sample_debris["debris_session_id"]) is not None
        assert db.get(TermsVersion, sample_debris["debris_terms_id"]) is not None
    # Counts should still reflect what WOULD have been deleted
    assert stats["courses"] >= 1
    assert stats["live_sessions"] >= 1
    assert stats["terms_versions"] >= 1


def test_cleanup_is_idempotent():
    """A second pass on an already-clean DB returns all zeros."""
    with SessionLocal() as db:
        tick(db)  # ensure clean
    with SessionLocal() as db:
        stats = tick(db)
    assert stats == {"courses": 0, "live_sessions": 0, "certificates": 0,
                     "terms_versions": 0, "outbox_messages": 0,
                     "course_views": 0, "marketplace_optouts": 0}
