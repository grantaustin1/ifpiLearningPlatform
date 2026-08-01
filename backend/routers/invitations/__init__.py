"""Admin invitations: create/list/revoke + public token endpoints (lookup, accept)."""
from fastapi import APIRouter

admin_router = APIRouter(prefix="/api/admin/invitations", tags=["Invitations"])
public_router = APIRouter(prefix="/api/invitations", tags=["Invitations"])

from . import _admin_routes, _public_routes  # noqa: E402, F401

