"""Iter 30n — factory-boy fixtures.

Drop-in factories for common domain models. Usage:

    from tests.factories import UserFactory, CourseFactory, EnrollmentFactory

    def test_thing():
        org = OrganizationFactory()
        user = UserFactory(organization_id=org.id)
        course = CourseFactory(organization_id=org.id)
        enrol = EnrollmentFactory(user_id=user.id, course_id=course.id)

We use plain FK IDs (not SQLAlchemy relationships) because several
IFPI models don't declare `relationship("Organization")` back-refs,
which trips SubFactory's default behaviour. Passing `_id` explicitly
is unambiguous and works for every model.
"""
from __future__ import annotations

import factory
from factory import Faker, LazyAttribute
from factory.alchemy import SQLAlchemyModelFactory

from core.database import SessionLocal
from core.security import get_password_hash
from models import (
    Course, CourseStatus, Enrollment, EnrollmentStatus, Organization,
    OrganizationStatus, User, UserRole,
)


_session = SessionLocal()


class _Base(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = _session
        sqlalchemy_session_persistence = "commit"


class OrganizationFactory(_Base):
    class Meta:
        model = Organization

    name = Faker("company")
    slug = factory.LazyFunction(lambda: f"factory-org-{__import__('uuid').uuid4().hex[:10]}")
    status = OrganizationStatus.ACTIVE


class UserFactory(_Base):
    class Meta:
        model = User

    email = factory.LazyFunction(lambda: f"factory-{__import__('uuid').uuid4().hex[:12]}@example.com")
    name = Faker("name")
    password_hash = LazyAttribute(lambda _: get_password_hash("test-password-123"))
    is_active = True
    points = 0

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if "organization_id" not in kwargs:
            kwargs["organization_id"] = OrganizationFactory().id
        return super()._create(model_class, *args, **kwargs)


class AdminUserFactory(UserFactory):
    """Convenience: also creates a UserRole row with ADMIN."""

    @factory.post_generation
    def assign_admin(obj, create, extracted, **kwargs):  # noqa: N805
        if not create:
            return
        _session.add(UserRole(user_id=obj.id, role="ADMIN"))
        _session.commit()


class CourseFactory(_Base):
    class Meta:
        model = Course

    title = Faker("sentence", nb_words=4)
    description = Faker("paragraph")
    status = CourseStatus.PUBLISHED

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if "organization_id" not in kwargs:
            kwargs["organization_id"] = OrganizationFactory().id
        return super()._create(model_class, *args, **kwargs)


class EnrollmentFactory(_Base):
    class Meta:
        model = Enrollment

    status = EnrollmentStatus.IN_PROGRESS
    progress = 0.0

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if "user_id" not in kwargs:
            kwargs["user_id"] = UserFactory().id
        if "course_id" not in kwargs:
            kwargs["course_id"] = CourseFactory().id
        return super()._create(model_class, *args, **kwargs)
