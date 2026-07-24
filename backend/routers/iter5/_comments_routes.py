from __future__ import annotations

from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from models import CourseSlide, SlideComment, User

from . import comments_router
from ._schemas import CommentIn, CommentOut


@comments_router.get("/slides/{slide_id}/comments", response_model=List[CommentOut])
def list_comments(slide_id: int, db: Session = Depends(get_db),
                  current: CurrentUser = Depends(get_current_user)):
    rows = db.query(SlideComment).filter(
        SlideComment.slide_id == slide_id, SlideComment.is_deleted.is_(False),
    ).order_by(SlideComment.created_at.asc()).limit(200).all()
    return [CommentOut(
        id=c.id, slide_id=c.slide_id, user_id=c.user_id,
        user_name=db.query(User).filter(User.id == c.user_id).first().name if c.user_id else None,
        body=c.body, parent_id=c.parent_id, created_at=c.created_at,
    ) for c in rows]


@comments_router.post("/slides/{slide_id}/comments", response_model=CommentOut)
def add_comment(slide_id: int, body: CommentIn, db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    slide = db.query(CourseSlide).filter(CourseSlide.id == slide_id).first()
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    if not (body.body or "").strip():
        raise HTTPException(status_code=400, detail="Comment body required")
    c = SlideComment(
        slide_id=slide_id, user_id=current.id, body=body.body.strip()[:5000],
        parent_id=body.parent_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    user = db.query(User).filter(User.id == current.id).first()
    return CommentOut(
        id=c.id, slide_id=c.slide_id, user_id=c.user_id,
        user_name=user.name, body=c.body, parent_id=c.parent_id, created_at=c.created_at,
    )


@comments_router.delete("/slides/{slide_id}/comments/{comment_id}")
def delete_comment(slide_id: int, comment_id: int, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)):
    c = db.query(SlideComment).filter(
        SlideComment.id == comment_id, SlideComment.slide_id == slide_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found")
    is_admin = current.has_any_role({"ADMIN", "SUPER_ADMIN", "INSTRUCTOR"})
    if c.user_id != current.id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    c.is_deleted = True
    c.body = "[deleted]"
    db.commit()
    return {"ok": True}
