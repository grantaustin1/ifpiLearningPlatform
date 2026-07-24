from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import OutboxMessage

from . import outbox_router


@outbox_router.get("")
def list_outbox(
    page: int = 1,
    page_size: int = 25,
    status: Optional[str] = None,
    template: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    query = db.query(OutboxMessage).filter(
        OutboxMessage.organization_id == current.organization_id,
    )
    if status:
        query = query.filter(OutboxMessage.status == status.upper())
    if template:
        query = query.filter(OutboxMessage.template == template)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (OutboxMessage.to_email.ilike(like)) | (OutboxMessage.subject.ilike(like)),
        )
    total = query.count()
    rows = query.order_by(OutboxMessage.created_at.desc())\
                .offset((page - 1) * page_size).limit(page_size).all()
    return {
        "messages": [{
            "id": m.id, "to_email": m.to_email, "to_name": m.to_name,
            "subject": m.subject, "template": m.template, "status": m.status,
            "transport": m.transport, "error": m.error,
            "attachments": m.attachments, "created_at": m.created_at,
            "sent_at": m.sent_at,
        } for m in rows],
        "page": page, "page_size": page_size, "total": total,
        "total_pages": (total + page_size - 1) // page_size if page_size else 1,
    }


@outbox_router.get("/stats")
def outbox_stats(db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    from sqlalchemy import func as sa_func
    rows = db.query(OutboxMessage.status, sa_func.count(OutboxMessage.id)).filter(
        OutboxMessage.organization_id == current.organization_id,
    ).group_by(OutboxMessage.status).all()
    return {status: count for status, count in rows}


@outbox_router.post("/{message_id}/retry")
def retry_outbox(message_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Reset a FAILED or DEAD_LETTER message back to QUEUED so the worker
    picks it up on its next tick. Scoped to the caller's organization."""
    m = db.query(OutboxMessage).filter(
        OutboxMessage.id == message_id,
        OutboxMessage.organization_id == current.organization_id,
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    m.status = "QUEUED"
    m.attempt_count = 0
    m.next_attempt_at = None
    m.error = None
    db.commit()
    return {"ok": True, "id": m.id, "status": m.status}
