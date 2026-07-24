from __future__ import annotations

from . import router
from ._schemas import BadgeTierIn, BadgeTierUpdate

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import BadgeTier


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
    from services import audit_service
    audit_service.record(db, current, "BADGE_TIER_CREATED",
        target_type="badge_tier", target_id=str(t.id),
        metadata={"slug": t.slug, "label": t.label})
    db.commit()
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
    from services import audit_service
    audit_service.record(db, current, "BADGE_TIERS_REORDERED",
        target_type="organization", target_id=str(current.organization_id),
        metadata={"order": ids})
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
    from services import audit_service
    audit_service.record(db, current, "BADGE_TIER_UPDATED",
        target_type="badge_tier", target_id=str(t.id),
        metadata=body.model_dump(exclude_unset=True))
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
    snapshot = {"slug": t.slug, "label": t.label}
    db.delete(t)
    from services import audit_service
    audit_service.record(db, current, "BADGE_TIER_DELETED",
        target_type="badge_tier", target_id=str(tier_id), metadata=snapshot)
    db.commit()
    return {"ok": True}
