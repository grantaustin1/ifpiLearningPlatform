"""Small helpers for DB scalability under load (Iter 37).

Two utilities:
  - `advisory_lock(db, key1, key2)` — Postgres row-level serialization
    keyed on a caller-chosen pair (e.g. `(org_id, user_sub)`).
    Concurrent webhooks / SSO logins for the SAME user serialize
    cleanly outside the transaction; different users still run in
    parallel. **No-op on SQLite** (single-writer already serializes).
  - `retry_on_deadlock(fn)` — decorator that catches Postgres 40P01
    (deadlock) and 40001 (serialization failure), retries ONCE with
    50–200ms jitter, then re-raises. Cheap protection against transient
    lock contention under load spikes.

See ERP360_BOLT_ON_WORK_LIST.md and GO_LIVE_CHECKLIST.md
"Load-readiness" section for context.
"""
from __future__ import annotations

import functools
import logging
import random
import time
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Postgres SQLSTATE codes we consider retriable.
_RETRIABLE_SQLSTATES = {"40P01", "40001"}


def advisory_lock(db: Session, key1: int, key2: int) -> None:
    """Take a transactional Postgres advisory lock on `(key1, key2)`.

    Must be called inside an open transaction; the lock releases at
    commit/rollback. No-op on non-Postgres dialects (SQLite in preview
    doesn't need it — the whole DB is single-writer already).

    `key1` / `key2` are 32-bit signed ints. Callers typically hash the
    stable identifier (`org_id`, `user_sub`) into these two slots.
    """
    dialect = db.get_bind().dialect.name
    if dialect != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(:k1, :k2)"),
        {"k1": _to_int32(key1), "k2": _to_int32(key2)},
    )


def _to_int32(value: int | str) -> int:
    """Coerce arbitrary ints/strings to a stable int32 for advisory locks."""
    if isinstance(value, str):
        # Portable hash → int32
        value = abs(hash(value))
    return int(value) % (2**31 - 1)


def retry_on_deadlock(max_retries: int = 1,
                      base_delay_s: float = 0.05,
                      max_delay_s: float = 0.20) -> Callable:
    """Decorator: retry the wrapped function on Postgres deadlock/serialization
    failures. Retries `max_retries` times with jittered backoff, then
    re-raises the original error. Cheap under normal load (0 retries in
    the fast path); the wrapper cost is one try/except.

    Usage:
        @retry_on_deadlock()
        def apply_role_change(...): ...
    """
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except OperationalError as e:
                    sqlstate = getattr(getattr(e, "orig", None), "pgcode", None)
                    if sqlstate not in _RETRIABLE_SQLSTATES or attempts >= max_retries:
                        raise
                    attempts += 1
                    delay = random.uniform(base_delay_s, max_delay_s)
                    logger.warning(
                        "Retriable DB error (%s) in %s — retry %d/%d after %.0fms",
                        sqlstate, fn.__name__, attempts, max_retries, delay * 1000,
                    )
                    time.sleep(delay)
        return _wrapped
    return _decorator
