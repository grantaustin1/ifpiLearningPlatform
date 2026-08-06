"""API tokens router (Iter 21).

Admin-only endpoints for issuing/managing programmatic bearer tokens.
The plaintext token is returned EXACTLY ONCE — at creation time. All
subsequent reads only see the prefix + last_used_at + scopes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.api_tokens import mint_token, TOKEN_PREFIX
from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from core.role_registry import normalize_role_names
from models import ApiToken

router = APIRouter(prefix="/api/admin/api-tokens", tags=["API Tokens"])


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: List[str] = Field(default_factory=lambda: ["LEARNER"])
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365 * 5)


def _to_dict(t: ApiToken) -> dict:
    return {
        "id": t.id, "name": t.name,
        "prefix": f"{TOKEN_PREFIX}{t.prefix}",
        "scopes": t.scopes or [],
        "is_active": t.is_active,
        "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "created_by_id": t.created_by_id,
    }


@router.get("")
def list_tokens(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    rows = db.query(ApiToken).filter(
        ApiToken.organization_id == current.organization_id,
    ).order_by(ApiToken.id.desc()).all()
    return {"items": [_to_dict(t) for t in rows]}


@router.post("", status_code=201)
def create_token(
    body: ApiTokenCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    # Preserve scope tokens (contain `:`) verbatim; normalize role tokens.
    raw = body.scopes or []
    scope_tokens = [s for s in raw if isinstance(s, str) and ":" in s]
    role_tokens = normalize_role_names([s for s in raw if isinstance(s, str) and ":" not in s])
    scopes = role_tokens + scope_tokens
    if not scopes:
        raise HTTPException(status_code=400, detail="At least one scope is required")

    plaintext, prefix, token_hash = mint_token()
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    row = ApiToken(
        organization_id=current.organization_id,
        name=body.name.strip(),
        prefix=prefix,
        token_hash=token_hash,
        scopes=scopes,
        created_by_id=current.id,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    from services import audit_service
    audit_service.record(
        db, current, "API_TOKEN_CREATED",
        target_type="api_token", target_id=str(row.id),
        metadata={"name": row.name, "scopes": scopes,
                  "expires_in_days": body.expires_in_days},
    )
    db.commit()

    # Plaintext returned EXACTLY ONCE
    return {**_to_dict(row), "token": plaintext}


@router.post("/{token_id}/revoke")
def revoke_token(
    token_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    row = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.organization_id == current.organization_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    if not row.is_active:
        return {"ok": True, "already_revoked": True}
    row.is_active = False
    db.commit()

    from services import audit_service
    audit_service.record(
        db, current, "API_TOKEN_REVOKED",
        target_type="api_token", target_id=str(row.id),
        metadata={"name": row.name, "prefix": row.prefix},
    )
    db.commit()
    return {"ok": True, "id": row.id}


@router.delete("/{token_id}")
def delete_token(
    token_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    row = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.organization_id == current.organization_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ── Iter P2 — 30-day usage analytics ────────────────────────────────
@router.get("/analytics/usage")
def token_usage_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    """Return per-day request counts for the org over the last `days` days,
    plus a breakdown by-token. Used by the /tokens page chart.

    Response shape:
      {
        "days": 30,
        "series": [{"date": "2026-06-15", "count": 42, "errors": 3}, ...],
        "by_token": [{"token_id": 1, "prefix": "abc123", "name": "CI bot", "count": 100}, ...],
        "total_calls": 1234, "total_errors": 12,
      }
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import case, func
    from models import ApiToken, ApiTokenCall

    days = max(1, min(days, 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Per-day aggregation
    date_col = func.date(ApiTokenCall.created_at)
    day_rows = (
        db.query(
            date_col.label("d"),
            func.count(ApiTokenCall.id).label("count"),
            func.sum(case((ApiTokenCall.status_code >= 400, 1), else_=0)).label("errors"),
        )
        .filter(
            ApiTokenCall.organization_id == current.organization_id,
            ApiTokenCall.created_at >= cutoff,
        )
        .group_by(date_col)
        .order_by(date_col.asc())
        .all()
    )
    # Fill zero-days so the chart renders a continuous 30-day axis
    lookup = {str(r.d): (int(r.count), int(r.errors or 0)) for r in day_rows}
    series = []
    total_calls = total_errors = 0
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        c, e = lookup.get(d, (0, 0))
        series.append({"date": d, "count": c, "errors": e})
        total_calls += c
        total_errors += e

    by_token_rows = (
        db.query(
            ApiTokenCall.api_token_id.label("tid"),
            func.count(ApiTokenCall.id).label("count"),
        )
        .filter(
            ApiTokenCall.organization_id == current.organization_id,
            ApiTokenCall.created_at >= cutoff,
        )
        .group_by(ApiTokenCall.api_token_id)
        .order_by(func.count(ApiTokenCall.id).desc())
        .limit(20)
        .all()
    )
    tid_map = {t.id: t for t in db.query(ApiToken).filter(
        ApiToken.id.in_([r.tid for r in by_token_rows] or [0])
    ).all()}
    by_token = [
        {"token_id": r.tid,
         "prefix": (tid_map.get(r.tid).prefix if tid_map.get(r.tid) else "-"),
         "name": (tid_map.get(r.tid).name if tid_map.get(r.tid) else "(deleted)"),
         "count": int(r.count)}
        for r in by_token_rows
    ]
    return {
        "days": days,
        "series": series,
        "by_token": by_token,
        "total_calls": total_calls,
        "total_errors": total_errors,
    }


@router.get("/analytics/spend")
def ai_spend_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    """Per-day $ spend across all AI providers for the last `days` days.
    Sources: `ai_usage_ledger`. Grouped by provider for a stacked chart."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    from models import AIUsageLedger

    days = max(1, min(days, 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    date_col = func.date(AIUsageLedger.created_at)
    rows = (
        db.query(
            date_col.label("d"),
            AIUsageLedger.provider.label("p"),
            func.sum(AIUsageLedger.cost_cents).label("cents"),
        )
        .filter(
            AIUsageLedger.organization_id == current.organization_id,
            AIUsageLedger.created_at >= cutoff,
        )
        .group_by(date_col, AIUsageLedger.provider)
        .all()
    )
    # Zero-fill each day; keep per-provider breakdown
    providers = sorted({r.p for r in rows})
    day_map: dict[str, dict[str, int]] = {}
    for r in rows:
        d = str(r.d)
        day_map.setdefault(d, {p: 0 for p in providers})[r.p] = int(r.cents or 0)

    series = []
    total_cents = 0
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        entry = {"date": d, "total_cents": 0}
        for p in providers:
            v = day_map.get(d, {}).get(p, 0)
            entry[p] = v
            entry["total_cents"] += v
        total_cents += entry["total_cents"]
        series.append(entry)

    # Per-provider totals for the doughnut / legend
    by_provider = [
        {"provider": p,
         "cost_cents": sum(day_map.get(d, {}).get(p, 0) for d in day_map)}
        for p in providers
    ]

    # Fetch org budget for context
    from services import ai_budget_service
    budget = ai_budget_service.get_budget_status(db, current.organization_id)

    return {
        "days": days,
        "providers": providers,
        "series": series,
        "by_provider": by_provider,
        "total_cents": total_cents,
        "budget": budget,
    }
