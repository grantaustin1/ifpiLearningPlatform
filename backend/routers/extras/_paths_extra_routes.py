from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import LearningPath

from . import paths_extra_router


@paths_extra_router.patch("/{path_id}/items/reorder")
def reorder_path_items(path_id: int, body: dict, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Accepts {"item_ids": [id1, id2, ...]}."""
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Path not found")
    ids = body.get("item_ids") or []
    items = {i.id: i for i in p.items}
    for idx, iid in enumerate(ids, start=1):
        if iid in items:
            items[iid].order_index = idx
    db.commit()
    return {"ok": True, "count": len(ids)}
