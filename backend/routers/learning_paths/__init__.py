"""Learning Paths router — group ordered courses with prerequisites.

Public endpoints (any authenticated user):
  GET    /api/learning-paths             list (LEARNERs see only PUBLISHED)
  GET    /api/learning-paths/{id}        detail with items
  POST   /api/learning-paths/{id}/enroll enrol in path

Admin endpoints (INSTRUCTOR/ADMIN):
  POST   /api/learning-paths              create
  PATCH  /api/learning-paths/{id}         update
  DELETE /api/learning-paths/{id}         delete
  POST   /api/learning-paths/{id}/items   add course to path
  DELETE /api/learning-paths/{id}/items/{course_id} remove
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/learning-paths", tags=["Learning Paths"])

from . import _routes  # noqa: E402, F401
