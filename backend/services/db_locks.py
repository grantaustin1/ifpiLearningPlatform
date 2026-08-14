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

# Re-exports so that when `@retry_on_deadlock` wraps a FastAPI endpoint
# using `from __future__ import annotations`, FastAPI's `get_type_hints`
# call — which inspects the wrapper's `__globals__` (this module) —
# can still resolve string-annotations like `request: Request`,
# `response: Response`, and `bg: BackgroundTasks`. Without these names
# being in scope here, FastAPI treats the param as a query param and
# 422s the endpoint. Keep this block in sync with the FastAPI ASGI
# types that `scripts/lint_endpoint_signatures.py --check-decorators`
# expects.
from fastapi import Request, Response, BackgroundTasks  # noqa: F401
from starlette.requests import Request as _StarletteRequest  # noqa: F401

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

        # FastAPI compatibility: when the decorated function's module uses
        # `from __future__ import annotations`, all annotations are stored as
        # strings.  FastAPI's `get_typed_signature` resolves those strings
        # against `_wrapped.__globals__` — which points to *this* module
        # (db_locks.py), not the original function's module.  Any type name
        # not imported here (e.g. `Request`, `CurrentUser`) is left as an
        # unresolved `ForwardRef`, which FastAPI then treats as a required
        # body/query parameter, causing a 422 on requests that don't supply
        # that parameter.
        #
        # Fix: for each *simple* (non-generic) string annotation in `fn`,
        # look up the name in `fn`'s own globals and, if it is a class,
        # inject it into `_wrapped.__globals__` using `setdefault` so we
        # never overwrite names already defined in this module.
        # We restrict injection to `type` instances to avoid leaking
        # arbitrary module-level objects from the caller's namespace.
        # Note: generic annotations such as `List[Request]` contain nested
        # names that are not injected by this loop; in practice the route
        # handlers in this codebase only use simple type names here.
        fn_globals = getattr(fn, "__globals__", {})
        for _annotation in getattr(fn, "__annotations__", {}).values():
            if (
                isinstance(_annotation, str)
                and _annotation in fn_globals
                and isinstance(fn_globals[_annotation], type)
            ):
                _wrapped.__globals__.setdefault(_annotation, fn_globals[_annotation])
        return _wrapped
    return _decorator
