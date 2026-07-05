"""Iter 30n — verify factory-boy fixtures work in isolation."""
from __future__ import annotations

from tests.factories import (
    CourseFactory, EnrollmentFactory, OrganizationFactory, UserFactory,
)


def test_org_factory_creates_row():
    org = OrganizationFactory()
    assert org.id
    assert org.name
    assert org.slug


def test_user_factory_creates_row_with_password():
    u = UserFactory()
    assert u.id
    assert u.email
    assert u.organization_id
    # Password hash is bcrypt-formatted
    assert u.password_hash.startswith("$2b$") or u.password_hash.startswith("$2a$")


def test_course_factory_belongs_to_org():
    c = CourseFactory()
    assert c.id
    assert c.organization_id
    assert c.title


def test_enrollment_factory_wires_user_and_course():
    e = EnrollmentFactory()
    assert e.id
    assert e.user_id
    assert e.course_id
    assert e.progress == 0.0


def test_factory_composition():
    """A single-line integration setup: user + course in same org + enrollment."""
    org = OrganizationFactory()
    user = UserFactory(organization_id=org.id)
    course = CourseFactory(organization_id=org.id)
    enrol = EnrollmentFactory(user_id=user.id, course_id=course.id)
    assert enrol.user_id == user.id
    assert enrol.course_id == course.id
    from models import Course, User
    from tests.factories import _session
    u = _session.query(User).filter_by(id=user.id).first()
    c = _session.query(Course).filter_by(id=course.id).first()
    assert u.organization_id == c.organization_id == org.id
