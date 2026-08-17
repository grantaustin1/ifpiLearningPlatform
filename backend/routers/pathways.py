"""Learner-facing qualification pathway map."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user
from core.database import get_db
from services.pathway_service import pathway_map

pathways_router = APIRouter(prefix="/api/pathways", tags=["Pathways"])


@pathways_router.get("/map")
def get_pathway_map(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    return pathway_map(db, current)
