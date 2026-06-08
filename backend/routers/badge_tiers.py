"""Badge tiers — per-organisation badge ladder CRUD + drag-reorder."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import BadgeTier

router = APIRouter(prefix="/api/badge-tiers", tags=["Badge Tiers"])


class BadgeTierIn(BaseModel):
    slug: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    emoji: str = Field(default="🏅", max_length=8)
    description: Optional[str] = None
    threshold_xp: int = 0
    is_active: bool = True


class BadgeTierUpdate(BaseModel):
    label: Optional[str] = None
    emoji: Optional[str] = None
    description: Optional[str] = None
    threshold_xp: Optional[int] = None
    is_active: Optional[bool] = None


def _to_dict(t: BadgeTier) -> dict:
    return {
        "id": t.id, "slug": t.slug, "label": t.label, "emoji": t.emoji or "🏅",
        "description": t.description, "threshold_xp": t.threshold_xp,
        "order_index": t.order_index, "is_active": t.is_active,
    }


@router.get("")
def list_tiers(db: Session = Depends(get_db),
               current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(BadgeTier).filter(
        BadgeTier.organization_id == current.organization_id,
    ).order_by(BadgeTier.order_index.asc(), BadgeTier.id.asc()).all()
    return [_to_dict(t) for t in rows]


@router.post("", status_code=201)
def create_tier(body: BadgeTierIn, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    slug = body.slug.strip().upper().replace(" ", "_")
    exists = db.query(BadgeTier).filter(
        BadgeTier.organization_id == current.organization_id,
        BadgeTier.slug == slug,
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"A tier with slug '{slug}' already exists")
    next_order = (db.query(BadgeTier).filter(
        BadgeTier.organization_id == current.organization_id,
    ).count())
    t = BadgeTier(
        organization_id=current.organization_id, slug=slug, label=body.label,
        emoji=body.emoji or "🏅", description=body.description,
        threshold_xp=body.threshold_xp, is_active=body.is_active,
        order_index=next_order,
    )
    db.add(t); db.commit(); db.refresh(t)
    return _to_dict(t)


@router.patch("/reorder")
def reorder_tiers(body: dict, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    ids = body.get("tier_ids") or []
    rows = db.query(BadgeTier).filter(
        BadgeTier.id.in_(ids),
        BadgeTier.organization_id == current.organization_id,
    ).all()
    by_id = {t.id: t for t in rows}
    for idx, tid in enumerate(ids):
        if tid in by_id:
            by_id[tid].order_index = idx
    db.commit()
    return {"ok": True, "updated": len(rows)}


@router.patch("/{tier_id}")
def update_tier(tier_id: int, body: BadgeTierUpdate, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    t = db.query(BadgeTier).filter(
        BadgeTier.id == tier_id,
        BadgeTier.organization_id == current.organization_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tier not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit(); db.refresh(t)
    return _to_dict(t)


@router.delete("/{tier_id}")
def delete_tier(tier_id: int, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    t = db.query(BadgeTier).filter(
        BadgeTier.id == tier_id,
        BadgeTier.organization_id == current.organization_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tier not found")
    db.delete(t); db.commit()
    return {"ok": True}
