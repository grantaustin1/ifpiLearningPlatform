"""AI flashcards — authoring (staff) + learner-side spaced-repetition (Iter 25).

Two routers in one module:

  `authoring_router`  (staff-only, /api/authoring/flashcards/*)
    - POST /generate        preview cards without persisting
    - POST /bulk-save       persist reviewed cards
    - GET  /by-course/{id}  list all cards for a course
    - PATCH /{card_id}      edit a card
    - DELETE /{card_id}     remove a card

  `learner_router`  (any auth'd user, /api/learn/flashcards/*)
    - GET  /courses/{course_id}/due     due-today queue (respects enrolment)
    - POST /{card_id}/review            SM-2 review with quality 0-5
    - GET  /courses/{course_id}/stats   completion stats (mastered / due / new)

Learners can only review cards for courses they are enrolled in — enforced
per-endpoint to avoid data leaks between orgs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_staff
from core.database import get_db
from models import (
    Course, CourseSlide, Enrollment, Flashcard, FlashcardReview,
    SourceChunk, SourceDocument,
)
from services import ai_budget_service, flashcard_service

logger = logging.getLogger("ifpi.flashcards")


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite stores DateTime naive — coerce to UTC-aware for safe comparison."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ─── AUTHORING (staff) ────────────────────────────────────────────────
authoring_router = APIRouter(
    prefix="/api/authoring/flashcards",
    tags=["AI Authoring"],
)


class GenerateFlashcardsIn(BaseModel):
    course_id: int
    slide_ids: Optional[List[int]] = None  # empty/None = whole course
    count: int = Field(default=8, ge=1, le=40)
    use_sources: bool = True               # augment with RAG source chunks


class CardIn(BaseModel):
    front: str = Field(min_length=1, max_length=500)
    back: str = Field(min_length=1, max_length=2000)
    hint: Optional[str] = Field(default=None, max_length=300)
    difficulty: int = Field(default=2, ge=1, le=5)
    tags: List[str] = []
    slide_id: Optional[int] = None
    source_chunk_ids: Optional[List[int]] = None


class BulkSaveIn(BaseModel):
    course_id: int
    cards: List[CardIn]


def _card_to_dict(c: Flashcard) -> dict:
    return {
        "id": c.id, "course_id": c.course_id, "slide_id": c.slide_id,
        "front": c.front, "back": c.back, "hint": c.hint,
        "difficulty": c.difficulty, "tags": c.tags or [],
        "generated_by_ai": c.generated_by_ai,
        "source_chunk_ids": c.source_chunk_ids or [],
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@authoring_router.post("/generate")
async def generate_flashcards(
    body: GenerateFlashcardsIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Preview AI-generated flashcards. Does NOT persist — the client shows a
    review table then calls `/bulk-save` with the edited list."""
    ai_budget_service.check_budget(db, current.organization_id,
                                    estimated_cost_cents=2)

    course = db.query(Course).filter(
        Course.id == body.course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    slides_q = db.query(CourseSlide).filter(CourseSlide.course_id == course.id)
    if body.slide_ids:
        slides_q = slides_q.filter(CourseSlide.id.in_(body.slide_ids))
    slides = slides_q.order_by(CourseSlide.order_index.asc()).all()
    if not slides:
        raise HTTPException(status_code=400,
                            detail="No slides matched — add lesson content first")

    slide_dicts = [
        {"title": s.title, "content": s.content or "", "id": s.id}
        for s in slides
    ]

    # Optional RAG augmentation from the org's SourceDocuments scoped to
    # this course (or org-wide when the source has no course_id).
    extra_context = None
    if body.use_sources:
        chunks = db.query(SourceChunk, SourceDocument).join(
            SourceDocument, SourceChunk.document_id == SourceDocument.id,
        ).filter(
            SourceDocument.organization_id == current.organization_id,
        ).filter(
            (SourceDocument.course_id == course.id) | (SourceDocument.course_id.is_(None))
        ).limit(6).all()
        if chunks:
            extra_context = "\n\n".join(
                f"[{doc.title}] {chunk.text[:600]}"
                for chunk, doc in chunks
            )

    preview = await flashcard_service.generate_flashcards(
        course_title=course.title, slides=slide_dicts,
        count=body.count, extra_context=extra_context,
    )

    ai_budget_service.record_spend(
        db, organization_id=current.organization_id,
        user_id=current.id, provider="openai",
        model="gpt-4o-mini", cost_cents=1,
        input_tokens=sum(len(s["content"]) // 4 for s in slide_dicts),
        output_tokens=sum(len(c["front"]) // 4 + len(c["back"]) // 4 for c in preview),
    )
    from services import audit_service
    audit_service.record(
        db, current, "AI_FLASHCARDS_GENERATED",
        target_type="course", target_id=str(course.id),
        metadata={"requested": body.count, "returned": len(preview),
                  "slide_count": len(slide_dicts)},
    )
    db.commit()

    return {"course_id": course.id, "course_title": course.title,
            "cards": preview}


@authoring_router.post("/bulk-save")
def bulk_save_flashcards(
    body: BulkSaveIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    """Persist a reviewed batch. Overwrites nothing — creates fresh rows."""
    course = db.query(Course).filter(
        Course.id == body.course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    created: List[Flashcard] = []
    for c in body.cards:
        fc = Flashcard(
            organization_id=current.organization_id,
            course_id=course.id,
            slide_id=c.slide_id,
            front=c.front.strip(), back=c.back.strip(),
            hint=(c.hint or None),
            difficulty=c.difficulty,
            tags=[t.strip() for t in c.tags if t.strip()][:6],
            generated_by_ai=True,
            source_chunk_ids=c.source_chunk_ids or [],
            created_by_id=current.id,
        )
        db.add(fc)
        created.append(fc)
    db.commit()
    for fc in created:
        db.refresh(fc)

    from services import audit_service
    audit_service.record(
        db, current, "AI_FLASHCARDS_SAVED",
        target_type="course", target_id=str(course.id),
        metadata={"saved": len(created)},
    )
    db.commit()
    return {"saved": len(created), "cards": [_card_to_dict(c) for c in created]}


@authoring_router.get("/by-course/{course_id}")
def list_by_course(
    course_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == current.organization_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    rows = db.query(Flashcard).filter(
        Flashcard.course_id == course.id,
        Flashcard.organization_id == current.organization_id,
    ).order_by(Flashcard.id.desc()).all()
    return {"course_id": course.id, "items": [_card_to_dict(c) for c in rows]}


class CardUpdateIn(BaseModel):
    front: Optional[str] = Field(default=None, max_length=500)
    back: Optional[str] = Field(default=None, max_length=2000)
    hint: Optional[str] = Field(default=None, max_length=300)
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    tags: Optional[List[str]] = None


@authoring_router.patch("/{card_id}")
def update_card(
    card_id: int, body: CardUpdateIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    card = db.query(Flashcard).filter(
        Flashcard.id == card_id,
        Flashcard.organization_id == current.organization_id,
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    changed = False
    if body.front is not None:
        card.front = body.front.strip()[:500]; changed = True
    if body.back is not None:
        card.back = body.back.strip()[:2000]; changed = True
    if body.hint is not None:
        card.hint = body.hint.strip()[:300] or None; changed = True
    if body.difficulty is not None:
        card.difficulty = body.difficulty; changed = True
    if body.tags is not None:
        card.tags = [t.strip() for t in body.tags if t.strip()][:6]; changed = True
    if changed:
        card.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(card)
    return _card_to_dict(card)


@authoring_router.delete("/{card_id}")
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_staff()),
):
    card = db.query(Flashcard).filter(
        Flashcard.id == card_id,
        Flashcard.organization_id == current.organization_id,
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    # Explicit cleanup of learner review rows — belt-and-braces so this
    # works on any DB engine irrespective of FK enforcement.
    db.query(FlashcardReview).filter(FlashcardReview.flashcard_id == card.id).delete()
    db.delete(card)
    db.commit()
    return {"ok": True, "id": card_id}


# ─── LEARNER (spaced repetition) ────────────────────────────────────
learner_router = APIRouter(
    prefix="/api/learn/flashcards",
    tags=["Learner Flashcards"],
)


def _ensure_learner_can_access(db: Session, user_id: int, org_id: int,
                                course_id: int) -> Course:
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.organization_id == org_id,
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # Enrolment isn't strictly required to preview cards — but we still
    # enforce org scope. Learners see their own org's published courses.
    return course


def _card_with_review(card: Flashcard, review: Optional[FlashcardReview]) -> dict:
    d = _card_to_dict(card)
    d["review"] = None if not review else {
        "ease_factor": round(review.ease_factor, 3),
        "interval_days": review.interval_days,
        "repetitions": review.repetitions,
        "next_review_at": review.next_review_at.isoformat() if review.next_review_at else None,
        "last_quality": review.last_quality,
        "review_count": review.review_count,
        "last_reviewed_at": review.last_reviewed_at.isoformat() if review.last_reviewed_at else None,
    }
    return d


@learner_router.get("/courses/{course_id}/due")
def due_flashcards(
    course_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Return the learner's due-today queue for a course. Mixes:
     - overdue/due cards ordered by earliest next_review_at first
     - up to `min(limit-due_count, new_cards)` never-seen cards to seed the deck
    """
    _ensure_learner_can_access(db, current.id, current.organization_id, course_id)

    now = datetime.now(timezone.utc)
    all_cards = db.query(Flashcard).filter(
        Flashcard.course_id == course_id,
        Flashcard.organization_id == current.organization_id,
    ).all()
    if not all_cards:
        return {"course_id": course_id, "cards": [], "due_count": 0,
                "new_count": 0, "total": 0}

    reviews = {
        r.flashcard_id: r
        for r in db.query(FlashcardReview).filter(
            FlashcardReview.user_id == current.id,
            FlashcardReview.flashcard_id.in_([c.id for c in all_cards]),
        ).all()
    }

    due, new_ = [], []
    for c in all_cards:
        r = reviews.get(c.id)
        if r is None:
            new_.append(c)
        elif _as_utc(r.next_review_at) <= now:
            due.append((_as_utc(r.next_review_at), c, r))
    due.sort(key=lambda t: t[0])   # earliest first

    slots = limit
    picks: List[dict] = []
    for _, c, r in due[:slots]:
        picks.append(_card_with_review(c, r))
    remaining = slots - len(picks)
    for c in new_[:remaining]:
        picks.append(_card_with_review(c, None))

    return {
        "course_id": course_id, "cards": picks,
        "due_count": len(due), "new_count": len(new_),
        "total": len(all_cards),
    }


class ReviewIn(BaseModel):
    quality: int = Field(ge=0, le=5)   # 0 = complete blackout, 5 = perfect


@learner_router.post("/{card_id}/review")
def review_flashcard(
    card_id: int, body: ReviewIn,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    card = db.query(Flashcard).filter(
        Flashcard.id == card_id,
        Flashcard.organization_id == current.organization_id,
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    review = db.query(FlashcardReview).filter(
        FlashcardReview.user_id == current.id,
        FlashcardReview.flashcard_id == card.id,
    ).first()

    now = datetime.now(timezone.utc)
    ease, interval, reps, next_at = flashcard_service.apply_sm2(
        quality=body.quality,
        ease=(review.ease_factor if review else 2.5),
        interval_days=(review.interval_days if review else 0),
        repetitions=(review.repetitions if review else 0),
    )
    if review:
        review.ease_factor = ease
        review.interval_days = interval
        review.repetitions = reps
        review.next_review_at = next_at
        review.last_quality = body.quality
        review.last_reviewed_at = now
        review.review_count += 1
    else:
        review = FlashcardReview(
            user_id=current.id, flashcard_id=card.id,
            ease_factor=ease, interval_days=interval, repetitions=reps,
            next_review_at=next_at, last_quality=body.quality,
            last_reviewed_at=now, review_count=1,
        )
        db.add(review)
    db.commit(); db.refresh(review)
    return {"card_id": card.id, "review": _card_with_review(card, review)["review"]}


@learner_router.get("/courses/{course_id}/stats")
def flashcard_stats(
    course_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    _ensure_learner_can_access(db, current.id, current.organization_id, course_id)
    all_cards = db.query(Flashcard).filter(
        Flashcard.course_id == course_id,
        Flashcard.organization_id == current.organization_id,
    ).all()
    if not all_cards:
        return {"course_id": course_id, "total": 0, "new": 0,
                "learning": 0, "mastered": 0, "due_now": 0}
    reviews = {
        r.flashcard_id: r
        for r in db.query(FlashcardReview).filter(
            FlashcardReview.user_id == current.id,
            FlashcardReview.flashcard_id.in_([c.id for c in all_cards]),
        ).all()
    }
    now = datetime.now(timezone.utc)
    new_ = learning = mastered = due_now = 0
    for c in all_cards:
        r = reviews.get(c.id)
        if r is None:
            new_ += 1
        else:
            if r.interval_days >= 21:
                mastered += 1
            else:
                learning += 1
            if _as_utc(r.next_review_at) <= now:
                due_now += 1
    return {
        "course_id": course_id, "total": len(all_cards),
        "new": new_, "learning": learning, "mastered": mastered,
        "due_now": due_now,
    }
