"""Prospect nurturing — nudge campaign signups who haven't started."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import (
    CampaignLink, CampaignSignup, Course, Enrollment, Organization, User,
)

logger = logging.getLogger(__name__)

DEFAULT_MESSAGE = (
    "Hi {name}, you created your account a few days ago but haven't started "
    "learning yet. Your first module is waiting — it only takes a few "
    "minutes to get going, and you're on the path to a professional "
    "qualification. Jump back in!"
)


def run_nurture_pass(db: Session, org_id: int | None = None) -> int:
    """Send one nudge per stale campaign signup. Returns nudges sent."""
    q = db.query(Organization).filter(Organization.nurture_enabled.is_(True))
    if org_id:
        q = q.filter(Organization.id == org_id)
    sent = 0
    for org in q.all():
        days = max(1, org.nurture_days or 3)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        stale = (db.query(CampaignSignup, User, CampaignLink)
                 .join(User, User.id == CampaignSignup.user_id)
                 .join(CampaignLink,
                       CampaignLink.id == CampaignSignup.campaign_link_id)
                 .filter(CampaignLink.organization_id == org.id,
                         CampaignSignup.nudged_at.is_(None),
                         CampaignSignup.created_at <= cutoff)
                 .all())
        for signup, user, link in stale:
            started = db.query(Enrollment).filter(
                Enrollment.user_id == user.id,
                Enrollment.progress > 0).first()
            if started:
                signup.nudged_at = datetime.now(timezone.utc).replace(tzinfo=None)
                continue
            course_title = None
            if link.auto_enroll_course_id:
                c = db.query(Course).filter(
                    Course.id == link.auto_enroll_course_id).first()
                course_title = c.title if c else None
            message = (org.nurture_message or DEFAULT_MESSAGE).replace(
                "{name}", user.name or "there").replace(
                "{course}", course_title or "your first course")
            try:
                from services.mail_service import MailService
                MailService(db).send_email(
                    to_email=user.email, to_name=user.name,
                    subject=f"Your learning journey at {org.name} is waiting",
                    body_html=f"<p>{message}</p>",
                    body_text=message, template="nurture_nudge",
                    organization_id=org.id, user_id=user.id)
            except Exception as ex:
                logger.warning("Nurture email failed for %s: %s", user.email, ex)
            try:
                from services.gamification_service import GamificationService
                GamificationService(db).notify(
                    user.id, "NURTURE_NUDGE",
                    "Pick up where you left off",
                    message, "/pathways")
            except Exception:
                pass
            signup.nudged_at = datetime.now(timezone.utc).replace(tzinfo=None)
            sent += 1
        db.commit()
    return sent
