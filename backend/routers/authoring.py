"""AI authoring root router — status + shared endpoints (Iter 22).

Feature-specific endpoints (`/tutor`, `/research`, `/quiz`, etc.) will
live in their own routers (e.g. `authoring_tutor.py`) but MUST also mount
under the same `/api/authoring/*` prefix so the frontend + rate-limiter +
audit filter can target the whole suite uniformly.

Every route in this router — and every future authoring router — MUST
use `requires_staff()` (not `requires_roles(...)` directly). Learners get
HTTP 403 by design (see docs/AI_AUTHORING_SUITE_ROADMAP.md §2).
"""
from __future__ import annotations

<<<<<<< HEAD
from typing import Optional
=======
>>>>>>> origin/main

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin, requires_staff
from core.config import settings
from core.database import get_db
from models import Organization
from services import ai_budget_service
from services.pii_redactor import redact, unredact

authoring_router = APIRouter(prefix="/api/authoring", tags=["AI Authoring"])


@authoring_router.get("/status")
def authoring_status(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Landing endpoint that the frontend hits when a staff user opens the
    authoring workspace. Returns:
      - budget snapshot (this month's spend + cap)
      - which feature flags are on for this org (all off by default in v1)
      - the roles that were accepted at auth time — so the UI can decide
        whether to show the "disable PII redaction" toggle.
    """
    return {
        "user": {
            "id": current.id, "email": current.email, "name": current.name,
            "roles": current.roles, "organization_id": current.organization_id,
        },
        "budget": ai_budget_service.get_budget_status(db, current.organization_id),
        "feature_flags": {
            # Iter 23 = tutor live; Iter 24 = research live (needs TAVILY_API_KEY);
            # Iter 25 = flashcards live. Others flip on per-iteration.
            "tutor_enabled": True,
            "deep_research_enabled": bool(settings.tavily_api_key),
            "flashcards_enabled": True,
            "video_overview_enabled": True,
            "tts_enabled": True,
            "visuals_enabled": True,
            "pptx_export_enabled": True,
        },
        "pii_redaction": {
            "default_on": True,     # locked policy (b)
            "user_can_disable": any(
                r in ("ADMIN", "SUPER_ADMIN") for r in current.roles
            ),
        },
    }


class RedactionPreviewIn(BaseModel):
    text: str
    unredact_probe: bool = False    # optional — round-trip test the mapping


@authoring_router.post("/redaction/preview")
def redaction_preview(
    body: RedactionPreviewIn,
    _current: CurrentUser = Depends(requires_staff()),
):
    """Small utility endpoint: shows staff exactly what PII gets stripped
    before their prompt is sent to a third-party LLM. Optional round-trip
    check verifies the mapping is lossless."""
    result = redact(body.text)
    response = {
        "redacted": result.redacted_text,
        "categories": result.counts,
        "mapping": result.mapping,       # placeholder -> original
        "applied": result.redaction_applied,
    }
    if body.unredact_probe:
        response["unredacted"] = unredact(result.redacted_text, result.mapping)
        response["lossless"] = response["unredacted"] == body.text
    return response


class BudgetUpdateIn(BaseModel):
    ai_monthly_budget_cents: int


@authoring_router.get("/budget")
def get_budget(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    return ai_budget_service.get_budget_status(db, current.organization_id)


@authoring_router.put("/budget")
def update_budget(
    body: BudgetUpdateIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_admin()),
):
    if body.ai_monthly_budget_cents < 0 or body.ai_monthly_budget_cents > 1_000_000_00:
        raise HTTPException(status_code=400,
                            detail="Budget must be 0 – $1,000,000")
    org = db.query(Organization).filter(
        Organization.id == current.organization_id,
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    old = org.ai_monthly_budget_cents
    org.ai_monthly_budget_cents = body.ai_monthly_budget_cents
    db.commit()

    from services import audit_service
    audit_service.record(
        db, current, "AI_BUDGET_UPDATED",
        target_type="organization", target_id=str(org.id),
        metadata={"old_cents": old, "new_cents": body.ai_monthly_budget_cents},
    )
    db.commit()
    return ai_budget_service.get_budget_status(db, current.organization_id)
