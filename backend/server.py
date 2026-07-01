"""IFPI LMS — FastAPI entry point.

Router registration is delegated to `routers.register_all` (Iter 20 refactor).
This file owns: app construction, CORS, lifecycle hooks, root + health.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, engine
from routers import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ifpi")

# Schema is managed by Alembic (`alembic upgrade head`). We also auto-create
# any missing tables on fresh checkouts; in production Alembic has already
# created everything so this is a no-op.
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

register_all(app)


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
    # Start the background outbox worker
    from services.outbox_worker import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    from services.outbox_worker import shutdown_scheduler
    shutdown_scheduler()
