"""Course routes: CRUD + slide management. Role-gated at the API layer."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/courses", tags=["Courses"])
richtext_router = APIRouter(prefix="/api/rich-text", tags=["Rich Text"])

from . import _course_routes, _slide_routes, _enrollment_routes, _prerequisite_routes, _richtext_routes
