"""Misc routes: AI builder, enrollments, certificates, notifications, leaderboard, analytics, billing, public catalog."""
from __future__ import annotations

from fastapi import APIRouter

ai_router = APIRouter(prefix="/api/ai", tags=["AI"])
enroll_router = APIRouter(prefix="/api/enrollments", tags=["Enrollments"])
cert_router = APIRouter(prefix="/api/certificates", tags=["Certificates"])
notif_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])
gam_router = APIRouter(prefix="/api/gamification", tags=["Gamification"])
admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])
billing_router = APIRouter(prefix="/api/billing", tags=["Billing"])
catalog_router = APIRouter(prefix="/api/catalog", tags=["Catalog"])

