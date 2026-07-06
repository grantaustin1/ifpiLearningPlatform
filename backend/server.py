"""IFPI LMS — FastAPI entry point.

Router registration is delegated to `routers.register_all` (Iter 20 refactor).
This file owns: app construction, CORS, lifecycle hooks, root + health.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Iter 32 · Sentry error tracking ─────────────────────────────────
# Initialised BEFORE any FastAPI app / router import so exceptions
# raised during startup are captured. No-op when SENTRY_DSN is unset,
# which is the case in dev / preview — Sentry never sees test noise.
_SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    def _sentry_before_send(event, hint):  # type: ignore[no-untyped-def]
        # Iter 32b — Attach the current correlation ID to every event.
        # `set_tag()` in CorrelationIdMiddleware handles the request-
        # scoped case, but background workers (APScheduler ticks,
        # outbox drainers) also get instrumented — this hook makes
        # sure they inherit whatever context var is set.
        try:
            from core.middleware import get_correlation_id
            cid = get_correlation_id()
            if cid:
                event.setdefault("tags", {}).setdefault("correlation_id", cid)
        except Exception:  # noqa: BLE001
            pass
        return event

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        environment=os.environ.get("ENVIRONMENT", "unknown"),
        release=os.environ.get("APP_RELEASE") or None,
        # Sample rate is intentionally conservative — 10% of transactions
        # for tracing. Errors are always captured at 100%.
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,  # never send PII/email/ip without consent
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            # LoggingIntegration turns every `logger.info/warning/...`
            # into a Sentry BREADCRUMB (default level=INFO), and every
            # `logger.error/exception` into a captured EVENT. Combined
            # with our correlation-id log format below, a single Sentry
            # error will show the full server-side trail of that same
            # request's log lines.
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        ignore_errors=[KeyboardInterrupt],
        before_send=_sentry_before_send,
    )

from core.config import settings
from core.database import Base, engine
from routers import register_all

# Structured log format — Iter 32b prepends the correlation ID (or a
# "-" placeholder when there isn't one, e.g. background workers). The
# Sentry LoggingIntegration turns each INFO+ line into a breadcrumb, so
# an error captured at request X now ships the FULL trail of log lines
# tagged with the same correlation-id.
#
# We inject `cid` via a LogRecordFactory (rather than a Filter) so it's
# populated on EVERY LogRecord — including ones emitted by third-party
# libraries (uvicorn, apscheduler, sqlalchemy) whose loggers may have
# their own handlers that bypass filter propagation.
_original_log_factory = logging.getLogRecordFactory()

def _record_factory(*args, **kwargs):
    record = _original_log_factory(*args, **kwargs)
    try:
        from core.middleware import get_correlation_id
        record.cid = get_correlation_id() or "-"
    except Exception:  # noqa: BLE001 — during import ordering
        record.cid = "-"
    return record

logging.setLogRecordFactory(_record_factory)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [cid=%(cid)s] %(name)s: %(message)s",
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


# ── Iter 28 · Rate limiting is per-router (in-memory sliding window). ─
# See routers/public_catalog.py::_ratelimit — no middleware needed.

# ── Iter 30d · Observability + brute-force lockout ─────────────────
# Adds correlation-ID header, global exception envelope, and rate-limits
# `/api/auth/login` at 5 failures / 15 min per email+IP combo.
from core.middleware import install_middleware
install_middleware(app)


# ── Iter P2 · API token call logger ────────────────────────────────
# Records one row in `api_token_calls` for every request authenticated
# with a bearer starting with our TOKEN_PREFIX. Only applied to /api/*.
@app.middleware("http")
async def _api_token_call_logger(request, call_next):
    import time
    from auth.api_tokens import TOKEN_PREFIX

    auth = request.headers.get("authorization") or ""
    is_token = (auth.lower().startswith("bearer ")
                and auth[7:].startswith(TOKEN_PREFIX)
                and request.url.path.startswith("/api/"))
    if not is_token:
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)

    # Fire-and-forget log — never let logging break the response
    try:
        from core.database import SessionLocal
        from models import ApiToken, ApiTokenCall
        import hashlib
        from auth.api_tokens import _hash as token_hash
        db = SessionLocal()
        try:
            row = db.query(ApiToken).filter(
                ApiToken.token_hash == token_hash(auth[7:]),
                ApiToken.is_active.is_(True),
            ).first()
            if row:
                db.add(ApiTokenCall(
                    organization_id=row.organization_id,
                    api_token_id=row.id,
                    path=request.url.path[:300],
                    method=request.method,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                ))
                db.commit()
        finally:
            db.close()
    except Exception:   # noqa: BLE001
        logger.exception("token-call logger failed (non-fatal)")

    return response


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
    from services.background_worker import shutdown_long_workers
    shutdown_scheduler()
    shutdown_long_workers(wait=False)
