"""In-process TTL cache with graceful-degrade on pool exhaustion
(Iter 38 Phase C).

Two components:

  cache_get(key)               — TTL lookup, returns None if expired/missing
  cache_set(key, value, ttl)   — insert with TTL
  cache_stale(key)             — return value even if expired, for
                                 stale-if-error fallback

  @cached_view(key_fn, ttl)    — decorator for GET handlers. Hot public
                                 reads (catalog, sync-status, feature
                                 flags) go through here.

  @degrade_on_db_error(cache_key_fn) — catches SQLAlchemy
     `OperationalError` (pool exhaustion, deadlock timeout) and returns
     the stale cached value with a `X-Served-Stale: true` header,
     rather than a 500.

Bounded memory (LRU eviction at 5k entries). Per-process, no cross-pod
consistency — that's fine for TTL-based hot-read caching where we're
happy to accept some staleness.
"""
from __future__ import annotations

import functools
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Optional

from fastapi import Request, Response, BackgroundTasks  # noqa: F401 — see lint_endpoint_signatures
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 5_000
_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()  # key → (expires_at, value)
_cache_lock = Lock()


def cache_get(key: str) -> Optional[Any]:
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < now:
            return None
        _cache.move_to_end(key)  # LRU: recently used → back
        return value


def cache_stale(key: str) -> Optional[Any]:
    """Return the value even if it's TTL-expired. Used by the
    graceful-degrade path when we'd rather return stale than error."""
    with _cache_lock:
        entry = _cache.get(key)
        return entry[1] if entry else None


def cache_set(key: str, value: Any, ttl_seconds: float) -> None:
    expires_at = time.time() + ttl_seconds
    with _cache_lock:
        _cache[key] = (expires_at, value)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)  # evict oldest


def cache_clear() -> None:
    with _cache_lock:
        _cache.clear()


def cache_delete(key: str) -> None:
    """Remove a single key from the cache (targeted invalidation)."""
    with _cache_lock:
        _cache.pop(key, None)


def cached_view(key_fn: Callable[..., str], ttl_seconds: float = 30.0):
    """Decorator: cache the JSON-serializable return value of a GET
    handler under a key derived from its arguments.

    `key_fn(*args, **kwargs) -> str` — must produce a stable, unique
    key. Only decorate SAFE endpoints (no user-scoped data unless the
    key includes the user id).

    Emits an `X-Cache: HIT` (or `MISS`) response header when a
    FastAPI `Response` is present in the handler kwargs — useful for
    ops and integration testing to verify the cache is wired.
    """
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            cached = cache_get(key)
            response = _find_response(args, kwargs)
            if cached is not None:
                if response is not None:
                    response.headers["X-Cache"] = "HIT"
                return cached
            result = fn(*args, **kwargs)
            cache_set(key, result, ttl_seconds)
            if response is not None:
                response.headers["X-Cache"] = "MISS"
            return result
        return _wrapped
    return _decorator


def _find_response(args: tuple, kwargs: dict) -> Optional[Response]:
    for arg in list(args) + list(kwargs.values()):
        if isinstance(arg, Response):
            return arg
    return None


def degrade_on_db_error(cache_key_fn: Callable[..., str]):
    """Decorator: if the wrapped handler raises SQLAlchemy
    OperationalError (pool exhaustion, statement timeout, deadlock),
    serve the most recent cached value with a `X-Served-Stale: true`
    header instead of returning 500.

    If nothing is cached, the original exception propagates.

    Only makes sense on GET handlers that also use `@cached_view`.
    """
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except OperationalError as exc:
                key = cache_key_fn(*args, **kwargs)
                stale = cache_stale(key)
                if stale is None:
                    logger.error("degrade: no stale cache for %s, re-raising", key)
                    raise
                logger.warning(
                    "degrade: DB unavailable (%s) — serving stale cache for %s",
                    type(exc.orig).__name__ if exc.orig else "OperationalError",
                    key,
                )
                # Try to stamp the header via a Response in kwargs
                for arg in list(args) + list(kwargs.values()):
                    if isinstance(arg, Response):
                        arg.headers["X-Served-Stale"] = "true"
                        break
                return stale
        return _wrapped
    return _decorator
