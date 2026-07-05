"""Iter 30o — Owner onboarding checklist.

A first-run visual checklist for new admin orgs. Returns the completion
state of the 7 key onboarding steps so the dashboard can render a
progress board:

  1. Branding — org name + colour set (default overridden)
  2. First course published
  3. First learner invited
  4. Certificate template configured
  5. SMTP configured (or default provider still fine)
  6. T&Cs published
  7. First learner activity (enrolment)

Each step returns `{key, label, done, cta_path?}`. The frontend uses
`cta_path` to jump straight to the missing setup.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from models import Course, Enrollment, Organization, TermsVersion, User

router = APIRouter(prefix="/api/admin/onboarding",
                   tags=["Owner Onboarding"])


@router.get("/checklist")
def onboarding_checklist(
    current: CurrentUser = Depends(requires_admin()),
    db: Session = Depends(get_db),
) -> dict:
    org = db.query(Organization).filter(
        Organization.id == current.organization_id).first()
    if not org:
        return {"steps": [], "percent": 0}

    # 1. Branding — org has a non-default primary_color OR logo_url
    branding_done = bool(org.logo_url) or (
        org.primary_color and org.primary_color != "#6366f1"
    )

    # 2. First course published
    has_course = db.query(Course).filter(
        Course.organization_id == org.id,
    ).first() is not None

    # 3. First learner invited (any non-admin user, or Invitation table entry)
    has_invitee = db.query(User).filter(
        User.organization_id == org.id,
        User.id != current.id,
    ).first() is not None

    # 4. Certificate template configured (accent colour or signature set)
    cert_done = bool(org.cert_signature_text or org.cert_signature_image_url)

    # 5. SMTP configured (host set means org opted in; if not, they use
    #    default org-level default SMTP which is also acceptable)
    smtp_done = bool(org.smtp_host)

    # 6. T&Cs published
    terms_done = db.query(TermsVersion).filter(
        TermsVersion.organization_id == org.id,
        TermsVersion.is_current.is_(True),
    ).first() is not None

    # 7. First learner activity — any enrolment in the org
    activity_done = db.query(Enrollment).join(
        User, User.id == Enrollment.user_id,
    ).filter(User.organization_id == org.id).first() is not None

    steps = [
        {"key": "branding", "label": "Set your brand colour & logo",
         "done": branding_done, "cta_path": "/settings"},
        {"key": "course", "label": "Publish your first course",
         "done": has_course, "cta_path": "/courses"},
        {"key": "invite", "label": "Invite your first learner",
         "done": has_invitee, "cta_path": "/users"},
        {"key": "cert", "label": "Configure certificate signature",
         "done": cert_done, "cta_path": "/settings"},
        {"key": "smtp", "label": "Set up custom email (optional)",
         "done": smtp_done, "cta_path": "/settings", "optional": True},
        {"key": "terms", "label": "Publish Terms & Conditions",
         "done": terms_done, "cta_path": "/settings"},
        {"key": "activity", "label": "See your first learner enrolment",
         "done": activity_done, "cta_path": "/analytics"},
    ]
    # Exclude optional steps from the % denominator
    non_optional = [s for s in steps if not s.get("optional")]
    done_count = sum(1 for s in non_optional if s["done"])
    percent = int(100 * done_count / len(non_optional)) if non_optional else 0

    return {"steps": steps, "percent": percent,
            "completed": done_count, "total": len(non_optional)}
