"""SQLAlchemy database setup.

Backend defaults to SQLite for local dev (`ifpi_lms.db`); flip `DATABASE_URL`
to a `postgresql://...` URL to use Postgres (no code changes needed) — this
matches the ERP360 pattern.
"""
from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.config import settings

logger = logging.getLogger(__name__)

connect_args = {}
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Postgres — tune the pool for a 4-worker uvicorn deployment.
    # Each worker holds `pool_size` conns + up to `max_overflow` extra.
    # At 4 workers × (20 + 10) = 120 conns to Postgres — sits comfortably
    # under PgBouncer or a modest RDS `max_connections=200`.
    import os as _os
    _engine_kwargs.update(
        pool_size=int(_os.environ.get("DB_POOL_SIZE", "20")),
        max_overflow=int(_os.environ.get("DB_MAX_OVERFLOW", "10")),
        pool_recycle=int(_os.environ.get("DB_POOL_RECYCLE_SECS", "1800")),
        pool_timeout=int(_os.environ.get("DB_POOL_TIMEOUT_SECS", "30")),
    )

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **_engine_kwargs,
)

# ── Iter 30d · Slow-query logger (only if not disabled) ────────────
if os.environ.get("SLOW_QUERY_ENABLED", "true").lower() in ("1", "true", "yes"):
    try:
        from core.slow_query_logger import install as _install_slow
        _install_slow(engine)
        # Iter 38 — per-request query counter for n+1 detection
        from core.query_counter import install as _install_qc
        _install_qc(engine)
    except Exception as _exc:  # noqa: BLE001
        logger.warning("slow-query logger install failed: %s", _exc)


# SQLite ignores FK constraints unless enabled per-connection. Without this
# our `ondelete=CASCADE` declarations are silently no-ops, leaving orphan
# rows behind (e.g. FlashcardReview after Flashcard delete). Postgres
# enforces this natively.
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_enable_fks(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
