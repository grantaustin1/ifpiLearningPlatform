"""AI budget enforcement (Iter 22).

Every LLM/media dispatch on the platform MUST:
1. Call `check_budget(db, org_id)` BEFORE issuing the external request.
   - Raises HTTPException(429) with a friendly detail if this month's spend
     already meets/exceeds `Organization.ai_monthly_budget_cents`.
2. Call `record_spend(db, ...)` AFTER the call returns, with real usage.

Aggregation is per (organization_id, billing_month="YYYY-MM"). We don't
pre-charge — spend is only recorded after the vendor call succeeds.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import AIUsageLedger, Organization

logger = logging.getLogger("ifpi.ai.budget")


def _current_billing_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def month_to_date_spend_cents(db: Session, organization_id: int) -> int:
    """Sum of AIUsageLedger.cost_cents for this org in the current month."""
    q = db.query(func.coalesce(func.sum(AIUsageLedger.cost_cents), 0)).filter(
        AIUsageLedger.organization_id == organization_id,
        AIUsageLedger.billing_month == _current_billing_month(),
    )
    return int(q.scalar() or 0)


def get_budget_status(db: Session, organization_id: int) -> dict:
    """Small dict for admin dashboards + the frontend budget chip."""
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        return {"error": "org_not_found"}
    spent = month_to_date_spend_cents(db, organization_id)
    budget = org.ai_monthly_budget_cents or 0
    return {
        "organization_id": organization_id,
        "billing_month": _current_billing_month(),
        "budget_cents": budget,
        "spent_cents": spent,
        "remaining_cents": max(budget - spent, 0),
        "percent_used": (spent / budget * 100) if budget else None,
        "over_budget": spent >= budget if budget else False,
    }


def check_budget(db: Session, organization_id: int,
                 estimated_cost_cents: int = 0) -> None:
    """Raise 429 if THIS call would push the org over budget. Callers pass
    an `estimated_cost_cents` when they know a lower-bound in advance (e.g.
    Sora is min $5 per clip)."""
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org or not org.ai_monthly_budget_cents:
        # No budget set → allow (org's cost is unmetered — up to Super Admin).
        return
    spent = month_to_date_spend_cents(db, organization_id)
    projected = spent + max(0, estimated_cost_cents)
    if projected >= org.ai_monthly_budget_cents:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "ai_budget_exceeded",
                "message": (
                    f"AI budget for {_current_billing_month()} exhausted "
                    f"(${spent / 100:.2f} / ${org.ai_monthly_budget_cents / 100:.2f}). "
                    "Ask an admin to raise the cap in Organisation settings."
                ),
                "spent_cents": spent,
                "budget_cents": org.ai_monthly_budget_cents,
            },
        )


def record_spend(
    db: Session, *, organization_id: int, provider: str, model: str,
    cost_cents: int, user_id: Optional[int] = None,
    job_id: Optional[int] = None,
    input_tokens: int = 0, output_tokens: int = 0,
) -> AIUsageLedger:
    """Persist a ledger row. Caller commits."""
    row = AIUsageLedger(
        organization_id=organization_id,
        user_id=user_id,
        job_id=job_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_cents=cost_cents,
        billing_month=_current_billing_month(),
    )
    db.add(row)
    db.flush()
    logger.info(
        "ai_spend org=%s provider=%s model=%s tokens=%s/%s cost_cents=%s",
        organization_id, provider, model, input_tokens, output_tokens, cost_cents,
    )
    return row
