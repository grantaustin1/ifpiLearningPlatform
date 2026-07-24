"""Badge tiers — per-organisation badge ladder CRUD + drag-reorder."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/badge-tiers", tags=["Badge Tiers"])

from . import _routes
