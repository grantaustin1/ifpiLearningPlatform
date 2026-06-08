"""IFPI LMS — FastAPI entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, engine
from routers import auth as auth_router
from routers import courses as courses_router
from routers import exams as exams_router
from routers import learning_paths as paths_router
from routers import misc as misc_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ifpi")

# Schema is managed by Alembic (`alembic upgrade head`).
# In dev we also auto-create any tables that don't exist yet (e.g. before
# you've run migrations on a fresh checkout). In production this is a no-op
# because Alembic has already created everything.
import models  # noqa: F401  — ensures all models register on metadata
Base.metadata.create_all(bind=engine, checkfirst=True)

app = FastAPI(
    title="IFPI Learning Platform API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers (prefix-scoped to /api) ───────────────────────────────────
app.include_router(auth_router.router)
app.include_router(courses_router.router)
app.include_router(exams_router.router)
app.include_router(paths_router.router)
app.include_router(misc_router.ai_router)
app.include_router(misc_router.enroll_router)
app.include_router(misc_router.cert_router)
app.include_router(misc_router.notif_router)
app.include_router(misc_router.gam_router)
app.include_router(misc_router.admin_router)
app.include_router(misc_router.billing_router)
app.include_router(misc_router.catalog_router)


@app.get("/api")
def root():
    return {
        "name": "IFPI Learning Platform",
        "status": "ok",
        "environment": settings.environment,
        "sso_enabled": settings.sso_enabled,
        "billing_live_mode": settings.billing_live_mode,
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.on_event("startup")
def on_startup():
    # Seed minimal data if the DB is empty (idempotent).
    from seed.seed_minimal import run_if_empty
    run_if_empty()
