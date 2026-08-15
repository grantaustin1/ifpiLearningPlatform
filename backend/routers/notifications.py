"""User notification routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import (
    Notification,
)
from schemas import (
    NotificationOut,
)

logger = logging.getLogger(__name__)



# ── Notifications ────────────────────────────────────────────────────
notif_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@notif_router.get("")
def list_notifications(db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    rows = db.query(Notification).filter(
        Notification.user_id == current.id,
    ).order_by(Notification.created_at.desc()).limit(25).all()
    unread = sum(1 for n in rows if not n.is_read)
    return {
        "notifications": [NotificationOut.model_validate(n).model_dump() for n in rows],
        "unread_count": unread,
    }


@notif_router.patch("/read-all")
def mark_all_read(db: Session = Depends(get_db),
                  current: CurrentUser = Depends(get_current_user)):
    db.query(Notification).filter(
        Notification.user_id == current.id, Notification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


