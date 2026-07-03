"""Slow-query logger (Iter 30d).

Attaches to SQLAlchemy's engine and logs any query slower than
SLOW_QUERY_MS (default 500 ms). Zero overhead for fast queries — we
only stringify the SQL when we're about to log it.

Log format is designed for Grafana/Loki parsing:

    [slow-query] elapsed_ms=612 rows=1 statement=SELECT ... params={...}
                 correlation_id=abc123

correlation_id comes from `core.middleware.get_correlation_id` if a
request is in flight; otherwise "-".

Wire-up: `from core.slow_query_logger import install; install(engine)`
in `core/database.py` after `create_engine`.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from sqlalchemy import event

logger = logging.getLogger("ifpi.slow_query")

SLOW_QUERY_MS = float(os.environ.get("SLOW_QUERY_MS", "500"))


def install(engine: Any) -> None:
    """Attach slow-query listeners to `engine`. Idempotent — repeated
    calls have no effect."""
    if getattr(engine, "_ifpi_slow_query_installed", False):
        return
    engine._ifpi_slow_query_installed = True  # noqa: SLF001

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, params, context, executemany):
        context._ifpi_query_start = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, params, context, executemany):
        start = getattr(context, "_ifpi_query_start", None)
        if start is None:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms < SLOW_QUERY_MS:
            return
        try:
            from core.middleware import get_correlation_id
            cid = get_correlation_id() or "-"
        except Exception:  # noqa: BLE001
            cid = "-"
        # Truncate statement to keep log lines bounded
        stmt = " ".join(statement.split())
        if len(stmt) > 400:
            stmt = stmt[:400] + "…"
        rowcount = getattr(cursor, "rowcount", -1)
        logger.warning(
            "[slow-query] elapsed_ms=%d rows=%s statement=%s params=%s "
            "correlation_id=%s",
            int(elapsed_ms), rowcount, stmt, params, cid,
        )
