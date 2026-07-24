"""Audit log read API + cohorts list + learner PDF transcript."""
from fastapi import APIRouter

router = APIRouter(tags=["Audit & Reports"])

from . import _routes
