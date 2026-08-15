"""Course ratings, reviews, replies and moderation."""
from __future__ import annotations


from fastapi import Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import (
    Course, Enrollment,
)
from routers.courses.common import (  # noqa: F401
    _can_manage, _detail, _summary, router,
)
@router.post("/{course_id}/rating")
def rate_course(course_id: int, body: dict, db: Session = Depends(get_db),
                current: CurrentUser = Depends(get_current_user)):
    """Rate a course you have COMPLETED (1-5 stars, upsert). Iter 44."""
    from models import CourseRating
    rating = body.get("rating")
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise HTTPException(status_code=422, detail="rating must be an integer 1-5")
    enr = db.query(Enrollment).filter(
        Enrollment.course_id == course_id, Enrollment.user_id == current.id,
        Enrollment.completed_at.isnot(None),
    ).first()
    if not enr:
        raise HTTPException(status_code=403, detail="Complete the course before rating it")
    row = db.query(CourseRating).filter(
        CourseRating.course_id == course_id, CourseRating.user_id == current.id,
    ).first()
    if row:
        row.rating = rating
        if "comment" in body:
            row.comment = body.get("comment") or None
    else:
        db.add(CourseRating(course_id=course_id, user_id=current.id,
                            rating=rating, comment=body.get("comment") or None))
    db.commit()
    avg, count = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)) \
        .filter(CourseRating.course_id == course_id).one()
    return {"ok": True, "my_rating": rating,
            "avg_rating": round(float(avg), 1) if avg else None, "rating_count": count}


@router.get("/{course_id}/rating")
def get_course_rating(course_id: int, db: Session = Depends(get_db),
                      current: CurrentUser = Depends(get_current_user)):
    """Average + count + the caller's own rating for a course."""
    from models import CourseRating
    avg, count = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)) \
        .filter(CourseRating.course_id == course_id).one()
    mine = db.query(CourseRating).filter(
        CourseRating.course_id == course_id, CourseRating.user_id == current.id,
    ).first()
    return {"avg_rating": round(float(avg), 1) if avg else None,
            "rating_count": count,
            "my_rating": mine.rating if mine else None,
            "my_comment": mine.comment if mine else None}


@router.get("/{course_id}/reviews")
def list_course_reviews(course_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """All written reviews for a course (incl. hidden) — admin moderation view. Iter 47."""
    from models import CourseRating, User
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    rows = (db.query(CourseRating, User.name, User.email)
            .join(User, User.id == CourseRating.user_id)
            .filter(CourseRating.course_id == course_id,
                    CourseRating.comment.isnot(None), CourseRating.comment != "")
            .order_by(CourseRating.created_at.desc()).all())
    return [{
        "id": r.id, "rating": r.rating, "comment": r.comment,
        "hidden": r.hidden_at is not None,
        "reply_text": r.reply_text,
        "reply_at": r.reply_at.isoformat() if r.reply_at else None,
        "reviewer_name": name or email,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r, name, email in rows]


@router.post("/{course_id}/reviews/{rating_id}/reply")
def reply_to_review(course_id: int, rating_id: int, body: dict,
                    db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Post/update a public academy reply under a learner review.
    Empty string clears the reply. Iter 48."""
    from datetime import datetime, timezone
    from models import CourseRating
    reply = body.get("reply")
    if not isinstance(reply, str) or len(reply) > 1000:
        raise HTTPException(status_code=422, detail="reply must be a string of at most 1000 characters")
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    row = db.query(CourseRating).filter(
        CourseRating.id == rating_id, CourseRating.course_id == course_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    reply = reply.strip()
    row.reply_text = reply or None
    row.reply_at = datetime.now(timezone.utc) if reply else None
    db.commit()
    return {"ok": True, "reply_text": row.reply_text,
            "reply_at": row.reply_at.isoformat() if row.reply_at else None}


@router.post("/{course_id}/reviews/{rating_id}/toggle-hidden")
def toggle_review_hidden(course_id: int, rating_id: int, db: Session = Depends(get_db),
                         current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Hide/unhide a written review from the public course page. Iter 47."""
    from datetime import datetime, timezone
    from models import CourseRating
    c = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == current.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    row = db.query(CourseRating).filter(
        CourseRating.id == rating_id, CourseRating.course_id == course_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    row.hidden_at = None if row.hidden_at else datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "hidden": row.hidden_at is not None}


