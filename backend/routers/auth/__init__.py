"""Auth routes: register, login, refresh, logout, /me, and the SSO bridge."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

from . import _routes  # noqa: E402, F401

