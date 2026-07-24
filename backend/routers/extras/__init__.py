"""Extras: public lead capture, org branding update, outbox audit, path reorder."""
from __future__ import annotations

from fastapi import APIRouter

leads_router = APIRouter(prefix="/api/leads", tags=["Leads"])
org_router = APIRouter(prefix="/api/organization", tags=["Organization"])
public_branding_router = APIRouter(prefix="/api/branding", tags=["Public Branding"])
outbox_router = APIRouter(prefix="/api/admin/outbox", tags=["Outbox"])
paths_extra_router = APIRouter(prefix="/api/learning-paths", tags=["Learning Paths"])

from . import (
    _leads_routes,
    _org_routes,
    _public_branding_routes,
    _outbox_routes,
    _paths_extra_routes,
)
