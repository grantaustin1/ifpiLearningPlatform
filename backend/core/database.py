"""SQLAlchemy database setup.

Backend defaults to SQLite for local dev (`ifpi_lms.db`); flip `DATABASE_URL`
to a `postgresql://...` URL to use Postgres (no code changes needed) — this
matches the ERP360 pattern.
"""
from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.config import settings

logger = logging.getLogger(__name__)

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)


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
