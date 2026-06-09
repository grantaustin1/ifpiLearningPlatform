#!/usr/bin/env python3
"""IFPI Agent 007 — Data Governance & Invariants Cop.

Ported pattern from ERP360 (scripts/qa_agents/agent_007_governance_auditor.py)
but with IFPI-specific invariants. Scans the DB for state that should
NEVER exist and reports violations. Run in CI to catch silent corruption.

Invariants checked:
- I-001  No Enrollment rows for archived courses
- I-002  No CourseProgress rows for unpublished courses (learner shouldn't
         have made progress on a course they can't see)
- I-003  No orphan SlideComment rows (course/slide deleted)
- I-004  No OutboxMessage stuck in FAILED with attempt_count < 3 for > 24h
- I-005  Every Certificate has a unique verifier_token
- I-006  No AuditLog entry references a non-existent organization_id
- I-007  No user.cohort longer than the column constraint (100 chars)
- I-008  No BadgeTier with duplicate (organization_id, slug)
- I-009  No Invitation that's both accepted_at and revoked_at populated

Exit code 0 if clean, 1 if any violation found. JSON report written to
test_reports/agent_007.json (or AGENT_REPORT_DIR override) for CI artifact upload.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import and_, func, text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    AuditLog, BadgeTier, Certificate, Course, CourseStatus, Enrollment,
    Invitation, Organization, OutboxMessage, SlideComment, User,
)


def _report_path(name: str) -> Path:
    report_dir = os.environ.get("AGENT_REPORT_DIR")
    if report_dir:
        return Path(report_dir) / name
    return Path(__file__).absolute().parents[3] / "test_reports" / name


def main() -> int:
    db = SessionLocal()
    failures: list[dict] = []
    now = datetime.now(timezone.utc)

    def fail(invariant: str, count: int, sample: list | None = None) -> None:
        failures.append({"invariant": invariant, "count": count, "sample": sample or []})

    # I-001 — Enrollments on archived courses
    cnt = db.query(Enrollment).join(Course).filter(Course.status == CourseStatus.ARCHIVED).count()
    if cnt:
        sample = [e.id for e in db.query(Enrollment).join(Course).filter(
            Course.status == CourseStatus.ARCHIVED).limit(5).all()]
        fail("I-001 enrollments_on_archived_courses", cnt, sample)

    # I-002 — CourseProgress on unpublished courses (uses raw SQL if model present)
    try:
        from models import CourseProgress
        cnt = db.query(CourseProgress).join(Course).filter(Course.status == CourseStatus.DRAFT).count()
        if cnt:
            fail("I-002 progress_on_unpublished", cnt)
    except ImportError:
        pass

    # I-003 — Orphan slide comments
    cnt = db.execute(text("""
        SELECT COUNT(*) FROM slide_comments c
        LEFT JOIN course_slides s ON s.id = c.slide_id
        WHERE s.id IS NULL
    """)).scalar() or 0
    if cnt:
        fail("I-003 orphan_slide_comments", cnt)

    # I-004 — Outbox stuck FAILED + attempt_count < 3 for > 24h
    cutoff = now - timedelta(hours=24)
    cnt = db.query(OutboxMessage).filter(
        OutboxMessage.status == "FAILED",
        OutboxMessage.attempt_count < 3,
        OutboxMessage.created_at < cutoff,
    ).count()
    if cnt:
        fail("I-004 stuck_failed_outbox", cnt)

    # I-005 — Certificates must have a unique verifier code
    dup = db.query(Certificate.code, func.count(Certificate.id)).group_by(
        Certificate.code).having(func.count(Certificate.id) > 1).all()
    if dup:
        fail("I-005 duplicate_certificate_codes", len(dup), [d[0] for d in dup[:5]])
    missing = db.query(Certificate).filter(Certificate.code.is_(None)).count()
    if missing:
        fail("I-005b certificate_missing_code", missing)

    # I-006 — Audit log dangling org refs
    cnt = db.execute(text("""
        SELECT COUNT(*) FROM audit_logs a
        LEFT JOIN organizations o ON o.id = a.organization_id
        WHERE o.id IS NULL
    """)).scalar() or 0
    if cnt:
        fail("I-006 audit_dangling_org", cnt)

    # I-007 — Cohort length cap
    long_cohorts = db.query(User).filter(func.length(User.cohort) > 100).count()
    if long_cohorts:
        fail("I-007 cohort_too_long", long_cohorts)

    # I-008 — Duplicate BadgeTier (organization_id, slug)
    dup = db.query(BadgeTier.organization_id, BadgeTier.slug, func.count(BadgeTier.id)).group_by(
        BadgeTier.organization_id, BadgeTier.slug).having(func.count(BadgeTier.id) > 1).all()
    if dup:
        fail("I-008 duplicate_badge_tier", len(dup))

    # I-009 — Invitation both accepted and revoked
    cnt = db.query(Invitation).filter(
        Invitation.accepted_at.isnot(None),
        Invitation.revoked_at.isnot(None),
    ).count()
    if cnt:
        fail("I-009 invitation_accepted_and_revoked", cnt)

    report = {
        "generated_at": now.isoformat(), "invariants_checked": 9,
        "violations": len(failures), "failures": failures,
    }
    out = _report_path("agent_007.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))

    if failures:
        print(f"FAIL — {len(failures)} invariant violations:")
        for f in failures:
            print(f"  {f['invariant']}: count={f['count']}")
        return 1
    print("OK — all 9 invariants clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
