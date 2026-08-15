"""Course lifecycle service — delete/publish/archive/duplicate business logic,
extracted from the router layer (audit P1: fat controllers)."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser
from core.cache import invalidate
from models import (
    Course, CourseSlide, CourseStatus, Enrollment, EnrollmentStatus,
)


class CourseLifecycleService:
    def __init__(self, db: Session):
        self.db = db

    def _get_owned(self, current: CurrentUser, course_id: int) -> Course:
        c = self.db.query(Course).filter(
            Course.id == course_id,
            Course.organization_id == current.organization_id,
        ).first()
        if not c:
            raise HTTPException(status_code=404, detail="Course not found")
        invalidate("catalog:")  # every lifecycle mutation affects the catalog
        return c

    def toggle_featured(self, current: CurrentUser, course_id: int) -> dict:
        c = self._get_owned(current, course_id)
        c.is_featured = not bool(c.is_featured)
        self.db.commit()
        return {"id": c.id, "is_featured": c.is_featured}

    def delete(self, current: CurrentUser, course_id: int) -> dict:
        db = self.db
        c = self._get_owned(current, course_id)
        if c.status == CourseStatus.PUBLISHED:
            raise HTTPException(
                status_code=409,
                detail="Unpublish the course first, then delete it")
        # Clean up FK dependents so the delete never 500s.
        from models import (
            AITutorSession, Certificate, CoursePrerequisite, CourseRating,
            CourseView, Exam, Flashcard, LearningPathItem, ScormPackage,
            SlideComment, SlideVersion, SlideView, SourceDocument, Subscription,
            LiveSession,
        )
        slide_ids = [s.id for s in c.slides]
        if slide_ids:
            for model in (SlideComment, SlideView, SlideVersion):
                db.query(model).filter(model.slide_id.in_(slide_ids)) \
                    .delete(synchronize_session=False)
            db.query(ScormPackage).filter(ScormPackage.slide_id.in_(slide_ids)) \
                .update({ScormPackage.slide_id: None}, synchronize_session=False)
        # Course-owned rows — hard delete alongside the course
        for model in (Flashcard, CourseRating, CourseView, LearningPathItem,
                      AITutorSession):
            db.query(model).filter(model.course_id == course_id) \
                .delete(synchronize_session=False)
        db.query(CoursePrerequisite).filter(
            (CoursePrerequisite.course_id == course_id)
            | (CoursePrerequisite.prerequisite_course_id == course_id)
        ).delete(synchronize_session=False)
        # Historical records — keep the row, detach the course reference
        for model in (Exam, Certificate, Subscription, SourceDocument,
                      LiveSession, ScormPackage):
            db.query(model).filter(model.course_id == course_id) \
                .update({model.course_id: None}, synchronize_session=False)
        db.delete(c)  # slides + enrollments cascade via ORM relationships
        from services import audit_service
        audit_service.record(db, current, "COURSE_DELETED",
                             target_type="course", target_id=course_id,
                             metadata={"title": c.title})
        db.commit()
        return {"ok": True}

    def publish(self, current: CurrentUser, course_id: int) -> dict:
        c = self._get_owned(current, course_id)
        if len(c.slides) == 0:
            raise HTTPException(status_code=400,
                                detail="Add at least one slide before publishing")
        c.status = CourseStatus.PUBLISHED
        self.db.commit()
        return {"ok": True, "status": c.status.value, "course_id": c.id,
                "title": c.title}

    def unpublish(self, current: CurrentUser, course_id: int) -> dict:
        c = self._get_owned(current, course_id)
        c.status = CourseStatus.DRAFT
        self.db.commit()
        return {"ok": True, "status": c.status.value}

    def archive(self, current: CurrentUser, course_id: int) -> dict:
        db = self.db
        c = self._get_owned(current, course_id)
        if c.status == CourseStatus.ARCHIVED:
            return {"ok": True, "status": c.status.value, "course_id": c.id}
        busy = db.query(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.IN_PROGRESS,
        ).count()
        if busy:
            raise HTTPException(
                status_code=409,
                detail=f"{busy} learner{'s are' if busy != 1 else ' is'} "
                       f"still busy with this course")
        c.status = CourseStatus.ARCHIVED
        from services import audit_service
        audit_service.record(db, current, "COURSE_ARCHIVED",
                             target_type="course", target_id=course_id,
                             metadata={"title": c.title})
        db.commit()
        return {"ok": True, "status": c.status.value, "course_id": c.id,
                "title": c.title}

    def unarchive(self, current: CurrentUser, course_id: int) -> dict:
        c = self._get_owned(current, course_id)
        if c.status != CourseStatus.ARCHIVED:
            raise HTTPException(status_code=409, detail="Course is not archived")
        c.status = CourseStatus.DRAFT
        from services import audit_service
        audit_service.record(self.db, current, "COURSE_UNARCHIVED",
                             target_type="course", target_id=course_id,
                             metadata={"title": c.title})
        self.db.commit()
        return {"ok": True, "status": c.status.value, "course_id": c.id,
                "title": c.title}

    def duplicate(self, current: CurrentUser, course_id: int) -> dict:
        db = self.db
        src = self._get_owned(current, course_id)
        new_course = Course(
            organization_id=src.organization_id,
            title=f"{src.title} (copy)",
            description=src.description, category=src.category,
            cover_color=src.cover_color, cover_image=src.cover_image,
            status=CourseStatus.DRAFT,
            passing_score=src.passing_score, duration_minutes=src.duration_minutes,
            price_cents=src.price_cents, currency=src.currency,
            created_by_id=current.id,
        )
        db.add(new_course)
        db.flush()
        for s in src.slides:
            db.add(CourseSlide(
                course_id=new_course.id, title=s.title, content=s.content,
                slide_type=s.slide_type, media_url=s.media_url,
                order_index=s.order_index, is_required=s.is_required,
                image_position=s.image_position, media_opacity=s.media_opacity,
            ))
        db.commit()
        db.refresh(new_course)
        return {
            "ok": True, "course_id": new_course.id, "title": new_course.title,
            "slides_copied": len(src.slides),
        }
