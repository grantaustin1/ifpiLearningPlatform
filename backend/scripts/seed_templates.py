"""IFPI template course seeder.

Creates 3 standardised "starter" template courses on a given organisation so
new tenants have a consistent authoring baseline:

  1. [TEMPLATE] Foundation      — a 5-slide intro-course scaffold
  2. [TEMPLATE] Practical       — hands-on module scaffold (video-heavy)
  3. [TEMPLATE] Assessment      — course + linked exam scaffold

Idempotent: if a template with the derived title already exists on the org,
we skip it. Safe to run multiple times.

Usage:
    python -m scripts.seed_templates --org-id 1
    python -m scripts.seed_templates --org-id 1 --admin-id 2   # explicit owner

If `--admin-id` is omitted, we pick (or create) `templates@system.local` on
the org. The templates land in status DRAFT + category "TEMPLATE" so they
don't leak into learner catalogs.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Tuple

# Ensure /app/backend is importable when invoked as a CLI script
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.database import SessionLocal  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from models import (  # noqa: E402
    Course, CourseSlide, CourseStatus, Organization, SlideType, User, UserRole,
)

logger = logging.getLogger("ifpi.seed_templates")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ── Template definitions ─────────────────────────────────────────────
# Each template = (title_suffix, description, [(slide_title, SlideType, content_html)])
TEMPLATES: List[Tuple[str, str, List[Tuple[str, SlideType, str]]]] = [
    (
        "Foundation",
        "Starter scaffold for onboarding-style courses. Duplicate this and "
        "replace the placeholders with your topic-specific content.",
        [
            ("Welcome", SlideType.TEXT,
             "<h2>Welcome to this course</h2>"
             "<p>Replace this text with a short paragraph introducing the "
             "topic, who the course is for, and what learners will be able "
             "to do by the end.</p>"),
            ("Learning objectives", SlideType.TEXT,
             "<h2>By the end of this course you will be able to…</h2>"
             "<ul><li>Objective 1</li><li>Objective 2</li>"
             "<li>Objective 3</li></ul>"),
            ("Core concepts", SlideType.TEXT,
             "<h2>Core concepts</h2>"
             "<p>Introduce the 3-5 key ideas. Use headings, bullets, and "
             "callout boxes. Add a linked video or diagram where it helps.</p>"),
            ("Worked example", SlideType.TEXT,
             "<h2>Worked example</h2>"
             "<p>Walk the learner through a concrete scenario applying the "
             "concepts above. Show reasoning steps, not just the answer.</p>"),
            ("Summary & next steps", SlideType.TEXT,
             "<h2>What you learned</h2>"
             "<ul><li>Key takeaway 1</li><li>Key takeaway 2</li></ul>"
             "<p>Next up: link to the Practical or Assessment course.</p>"),
        ],
    ),
    (
        "Practical",
        "Hands-on / demo-heavy scaffold. Slides alternate between short text "
        "briefings and a video demo placeholder.",
        [
            ("Practical overview", SlideType.TEXT,
             "<h2>What we'll practise</h2>"
             "<p>Describe the skill, why it matters, and the safety / prep "
             "steps the learner should complete before starting.</p>"),
            ("Demonstration", SlideType.VIDEO,
             "<p>Attach a demo video (mp4). Aim for &lt; 3 minutes. Show the "
             "correct technique end-to-end.</p>"),
            ("Common mistakes", SlideType.TEXT,
             "<h2>Watch out for…</h2>"
             "<ul><li>Common error 1 — how to spot it</li>"
             "<li>Common error 2 — how to correct it</li></ul>"),
            ("Guided practice", SlideType.TEXT,
             "<h2>Now you try</h2>"
             "<p>Step-by-step instructions the learner follows offline. "
             "Include a self-check list at the end.</p>"),
            ("Feedback checklist", SlideType.TEXT,
             "<h2>Self-assessment</h2>"
             "<p>Rate yourself against these criteria. If you fail any two, "
             "revisit the Demonstration slide.</p>"),
        ],
    ),
    (
        "Assessment",
        "Formal-assessment scaffold. Pair this with an Exam entity to give "
        "learners a graded certificate at the end.",
        [
            ("Assessment instructions", SlideType.TEXT,
             "<h2>Before you start</h2>"
             "<p>Explain the format, time limit, passing score, and how "
             "many attempts the learner has.</p>"),
            ("Prerequisites", SlideType.TEXT,
             "<h2>Prerequisites</h2>"
             "<p>List the Foundation + Practical courses that must be "
             "completed first.</p>"),
            ("Study checklist", SlideType.TEXT,
             "<h2>Recap before the exam</h2>"
             "<ul><li>Key concept 1</li><li>Key concept 2</li>"
             "<li>Key concept 3</li></ul>"),
            ("Ready?", SlideType.TEXT,
             "<h2>Take the assessment</h2>"
             "<p>When you feel ready, click <em>Start exam</em>. Good luck!"
             "</p>"),
        ],
    ),
]


def _get_or_create_admin(db, org_id: int, explicit_admin_id: int | None):
    """Return an admin User to attribute created content to."""
    if explicit_admin_id:
        u = db.query(User).filter(
            User.id == explicit_admin_id,
            User.organization_id == org_id,
        ).first()
        if not u:
            raise SystemExit(
                f"--admin-id={explicit_admin_id} not found on org {org_id}")
        return u

    # Reuse the same helper account that bulk_import.py uses when present.
    tpl_email = "templates@system.local"
    u = db.query(User).filter(
        User.email == tpl_email, User.organization_id == org_id,
    ).first()
    if u:
        return u

    u = User(
        organization_id=org_id, email=tpl_email, name="Template Seeder",
        password_hash=get_password_hash("!disabled-template-seeder!"),
        is_active=False,     # can't log in — audit-trail-only account
    )
    db.add(u)
    db.flush()
    db.add(UserRole(user_id=u.id, role="ADMIN"))
    db.flush()
    return u


def seed_org(org_id: int, admin_id: int | None = None) -> dict:
    """Create the 3 template courses on `org_id`. Idempotent — skips existing.

    Returns a summary dict: {created: [...], skipped: [...], errors: [...]}.
    """
    summary: dict = {"created": [], "skipped": [], "errors": []}
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise SystemExit(f"Organization id={org_id} not found")

        admin = _get_or_create_admin(db, org_id, admin_id)

        for title_suffix, description, slides in TEMPLATES:
            title = f"[TEMPLATE] {title_suffix}"

            existing = db.query(Course).filter(
                Course.organization_id == org_id,
                Course.title == title,
            ).first()
            if existing:
                summary["skipped"].append({
                    "title": title, "course_id": existing.id,
                    "reason": "already exists",
                })
                continue

            try:
                c = Course(
                    organization_id=org_id,
                    title=title,
                    description=description,
                    category="TEMPLATE",
                    status=CourseStatus.DRAFT,
                    created_by_id=admin.id,
                    price_cents=0,
                    duration_minutes=len(slides) * 5,   # rough estimate
                )
                db.add(c)
                db.flush()
                for idx, (slide_title, slide_type, content_html) in enumerate(slides, start=1):
                    db.add(CourseSlide(
                        course_id=c.id,
                        title=slide_title,
                        content=content_html,
                        slide_type=slide_type,
                        order_index=idx,
                        is_required=True,
                    ))
                db.flush()
                summary["created"].append({
                    "title": title, "course_id": c.id,
                    "slides": len(slides),
                })
                logger.info("Created template course '%s' (id=%d, %d slides)",
                            title, c.id, len(slides))
            except Exception as e:   # noqa: BLE001
                logger.exception("Failed to create template '%s'", title)
                summary["errors"].append({"title": title, "error": str(e)})
                db.rollback()

        db.commit()
    finally:
        db.close()
    return summary


def _cli() -> None:
    ap = argparse.ArgumentParser(
        description="Seed the 3 IFPI starter course templates on an org.")
    ap.add_argument("--org-id", type=int, required=True,
                    help="Target Organization id")
    ap.add_argument("--admin-id", type=int, default=None,
                    help="User id to attribute the templates to. Defaults to "
                         "a service account (templates@system.local).")
    args = ap.parse_args()

    result = seed_org(args.org_id, args.admin_id)
    print()
    print(f"Seeded org {args.org_id}:")
    print(f"  Created: {len(result['created'])}")
    for c in result["created"]:
        print(f"    - {c['title']} (course_id={c['course_id']}, "
              f"{c['slides']} slides)")
    print(f"  Skipped: {len(result['skipped'])}")
    for s in result["skipped"]:
        print(f"    - {s['title']} ({s['reason']})")
    print(f"  Errors:  {len(result['errors'])}")
    for e in result["errors"]:
        print(f"    - {e['title']}: {e['error']}")


if __name__ == "__main__":
    _cli()
