"""Per-request query counter (Iter 38, Phase A observability).

Instruments SQLAlchemy so every DB round-trip within a request scope
increments a per-correlation-id counter. The request latency
middleware reads that counter after the handler returns and:

  1. Logs it as part of the `[req]` line so we can grep for n+1.
  2. Emits it as the `X-Query-Count` response header (dev/staging only,
     via env `EXPOSE_QUERY_COUNT_HEADER=true`).

Design note: contextvars don't work here — SQLAlchemy runs sync DB
operations on anyio's threadpool, and contextvar mutations inside a
threadpool run don't propagate back to the async caller. We key on
`correlation_id` instead, which is set by the middleware BEFORE the
handler runs, propagates into the threadpool via context copy, and
gives us a stable per-request identifier the SQLAlchemy event hook
can read via `get_correlation_id()`.

Bounded memory: we cap the tracking dict at 10k live requests and
clean up in `reset_query_count()`. Under normal load the dict has
one entry per in-flight request.

Wire-up: `core.database.install_query_counter(engine)` after
`create_engine`. Read via `get_query_count()` from the middleware.
"""
from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import event

# Keyed on correlation_id. Bounded — we clear entries in
# reset_query_count() when a request finishes. The lock is required
# because SQLAlchemy events fire from the threadpool while the
# middleware writes from the event loop.
_counts: dict[str, int] = {}
_counts_lock = threading.Lock()
_MAX_LIVE_REQUESTS = 10_000


def reset_query_count() -> None:
    """Call at request start. Initializes the counter for the current
    correlation_id."""
    from core.middleware import get_correlation_id
    cid = get_correlation_id()
    if not cid:
        return
    with _counts_lock:
        # Prune if over budget — coarse but safe. Under real load this
        # never fires because entries are removed on request completion.
        if len(_counts) >= _MAX_LIVE_REQUESTS:
            _counts.clear()
        _counts[cid] = 0


def get_query_count() -> int:
    """Return count for the current correlation_id, or 0."""
    from core.middleware import get_correlation_id
    cid = get_correlation_id()
    if not cid:
        return 0
    with _counts_lock:
        return _counts.get(cid, 0)


def drop_query_count() -> None:
    """Call after logging the request summary — releases the entry."""
    from core.middleware import get_correlation_id
    cid = get_correlation_id()
    if not cid:
        return
    with _counts_lock:
        _counts.pop(cid, None)


def _increment(cid: str) -> None:
    with _counts_lock:
        if cid in _counts:  # only count requests we're actively tracking
            _counts[cid] += 1


def install(engine: Any) -> None:
    """Attach the per-query counter to `engine`. Idempotent."""
    if getattr(engine, "_ifpi_query_counter_installed", False):
        return
    engine._ifpi_query_counter_installed = True  # noqa: SLF001

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        try:
            from core.middleware import get_correlation_id
            cid = get_correlation_id()
            if cid:
                _increment(cid)
        except Exception:  # noqa: BLE001
            pass
