"""Idempotent UAT sandbox setup: dedicated org + admin + learner.

Run:  cd /app/backend && python scripts/setup_uat.py
Undo: bash /app/scripts/reset_uat.sh   (restores the pre-UAT DB snapshot)
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal
from core.security import get_password_hash
from models import LifecycleStage, Organization, Person, User, UserRole

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("setup_uat")

UAT_ADMIN_EMAIL = "uat-admin@ifpi.org"
UAT_ADMIN_PASSWORD = "UatAdmin!2026"
UAT_LEARNER_EMAIL = "uat-learner@ifpi.org"
UAT_LEARNER_PASSWORD = "UatLearner!2026"


def _ensure_user(db, org, email, password, name, role):
    user = db.query(User).filter(User.email == email).first()
    if user:
        log.info("• %s already exists (id=%s) — untouched", email, user.id)
        return user
    user = User(
        email=email, name=name,
        password_hash=get_password_hash(password),
        organization_id=org.id, is_active=True,
        must_change_password=False,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role=role))
    db.add(Person(user_id=user.id, organization_id=org.id,
                  email=email, name=name,
                  lifecycle_stage=LifecycleStage.LEARNER, source="uat_seed"))
    log.info("• created %s (%s, org=%s)", email, role, org.slug)
    return user


def main() -> None:
    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.slug == "uat-sandbox").first()
        if not org:
            org = Organization(
                name="UAT Sandbox", slug="uat-sandbox",
                description="Isolated tenant for pre-go-live team testing. "
                            "Safe to purge — never migrate to production.",
                primary_color="#0ea5e9",
                marketplace_opt_in=False,
            )
            db.add(org)
            db.flush()
            log.info("• created organization 'UAT Sandbox' (id=%s)", org.id)
        else:
            log.info("• organization 'UAT Sandbox' already exists (id=%s)", org.id)

        _ensure_user(db, org, UAT_ADMIN_EMAIL, UAT_ADMIN_PASSWORD, "UAT Admin", "ADMIN")
        _ensure_user(db, org, UAT_LEARNER_EMAIL, UAT_LEARNER_PASSWORD, "UAT Learner", "LEARNER")
        db.commit()

    log.info("")
    log.info("UAT sandbox ready.")
    log.info("  Admin:   %s / %s", UAT_ADMIN_EMAIL, UAT_ADMIN_PASSWORD)
    log.info("  Learner: %s / %s", UAT_LEARNER_EMAIL, UAT_LEARNER_PASSWORD)


if __name__ == "__main__":
    main()
