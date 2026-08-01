"""Iter 22 — Live Sessions router (decomposed package).

Endpoints:
- Admin:
    POST   /api/live-sessions               create
    PATCH  /api/live-sessions/{id}           update
    DELETE /api/live-sessions/{id}           cancel
    GET    /api/live-sessions                list (all in org)
    GET    /api/live-sessions/{id}           detail (with RSVPs + attendance)
    POST   /api/live-sessions/{id}/mark-attendance   bulk mark

- Learner:
    GET    /api/live-sessions/upcoming       upcoming sessions
    POST   /api/live-sessions/{id}/rsvp      toggle RSVP
    GET    /api/live-sessions/{id}/ics       download .ics
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/live-sessions", tags=["Live Sessions"])

from . import _attendance_routes, _ics_routes, _routes  # noqa: E402, F401
