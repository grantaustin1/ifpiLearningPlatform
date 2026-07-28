"""Course routes: CRUD + slide management. Role-gated at the API layer."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/courses", tags=["Courses"])
richtext_router = APIRouter(prefix="/api/rich-text", tags=["Rich Text"])

