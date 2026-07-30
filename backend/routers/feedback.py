"""In-app feedback widget (Iter 44) — any authed user submits; admins review."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from auth.dependencies import CurrentUser, get_current_user, requires_roles
from models import TesterFeedback, User

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])
admin_router = APIRouter(prefix="/api/admin/feedback", tags=["Feedback (admin)"])

_CATEGORIES = {"BUG", "IDEA", "OTHER"}


class FeedbackIn(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    category: str = "BUG"
    page: str | None = Field(default=None, max_length=300)


@router.post("", status_code=201)
def submit_feedback(body: FeedbackIn, db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    """Log an in-app feedback item (bug report, idea, other)."""
    category = body.category.upper()
    if category not in _CATEGORIES:
        raise HTTPException(status_code=422, detail="category must be BUG, IDEA or OTHER")
    row = TesterFeedback(
        organization_id=current.organization_id, user_id=current.id,
        page=body.page, category=category, message=body.message.strip(),
    )
    db.add(row)
    db.commit()
    return {"ok": True, "id": row.id}


@admin_router.get("")
def list_feedback(status: str | None = None, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """All feedback for the caller's org, newest first."""
    q = (db.query(TesterFeedback, User.name, User.email)
         .join(User, User.id == TesterFeedback.user_id)
         .filter(TesterFeedback.organization_id == current.organization_id))
    if status:
        q = q.filter(TesterFeedback.status == status.upper())
    rows = q.order_by(TesterFeedback.created_at.desc()).limit(500).all()
    return [{
        "id": f.id, "page": f.page, "category": f.category, "message": f.message,
        "status": f.status, "created_at": f.created_at.isoformat() if f.created_at else None,
        "user_name": name, "user_email": email,
    } for f, name, email in rows]


@admin_router.post("/{feedback_id}/status")
def set_feedback_status(feedback_id: int, body: dict, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Flip a feedback item between NEW and REVIEWED."""
    status = str(body.get("status", "")).upper()
    if status not in {"NEW", "REVIEWED"}:
        raise HTTPException(status_code=422, detail="status must be NEW or REVIEWED")
    row = (db.query(TesterFeedback)
           .filter(TesterFeedback.id == feedback_id,
                   TesterFeedback.organization_id == current.organization_id)
           .first())
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found")
    row.status = status
    db.commit()
    return {"ok": True, "id": row.id, "status": row.status}
