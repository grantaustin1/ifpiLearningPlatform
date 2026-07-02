"""Redis-backed sliding-window rate limiter with in-memory fallback (Iter 30b).

Why Redis? The in-memory limiter previously in `routers/public_catalog.py`
resets per-process, so it fails as soon as we scale to >1 uvicorn worker or
Kubernetes pod. Redis gives us a shared counter that survives restarts and
works across replicas.

Fallback: if Redis is unavailable (env var not set, connection refused,
Redis down) we transparently fall back to the same threading-based
in-memory sliding window we had before. Callers never see errors — the
limiter simply becomes local-only.

Public API:
    check(key, max_requests, window_secs) -> None
      Raises HTTPException(429) with a Retry-After header when the caller
      is over the limit. Otherwise records the hit and returns.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("ifpi.ratelimit")

# ── Redis client (lazy singleton) ───────────────────────────────────
_redis_client = None
_redis_disabled = False


def _get_redis():
    """Return a live Redis client or None. Cached across calls."""
    global _redis_client, _redis_disabled
    if _redis_disabled:
        return None
    if _redis_client is not None:
        return _redis_client
    url = os.environ.get("REDIS_URL")
    if not url:
        # TODO: In multi-pod prod, REDIS_URL must be set. Falling back to
        # in-memory limiter (per-process, resets on restart).
        logger.info("REDIS_URL not set — rate limiter falling back to in-memory")
        _redis_disabled = True
        return None
    try:
        import redis  # local import so unavailable redis-py doesn't crash boot
        cli = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1,
                                   decode_responses=False)
        cli.ping()
        _redis_client = cli
        logger.info("Rate limiter using Redis at %s", url)
        return cli
    except Exception as exc:  # noqa: BLE001 — any connection error → fallback
        logger.warning("Redis unavailable (%s) — falling back to in-memory limiter", exc)
        _redis_disabled = True
        return None


# ── In-memory fallback (single-process sliding window) ──────────────
_mem_buckets: dict[str, deque] = defaultdict(deque)
_mem_lock = threading.Lock()


def _check_in_memory(key: str, max_requests: int, window_secs: float) -> None:
    now = time.monotonic()
    with _mem_lock:
        bucket = _mem_buckets[key]
        while bucket and now - bucket[0] > window_secs:
            bucket.popleft()
        if len(bucket) >= max_requests:
            retry_after = int(window_secs - (now - bucket[0])) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many requests — try again shortly",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def _check_redis(cli, key: str, max_requests: int, window_secs: float) -> None:
    """Redis sorted-set sliding-window: score = timestamp, values also
    timestamp+nanoid. Remove expired, count, add current."""
    now_ms = int(time.time() * 1000)
    window_ms = int(window_secs * 1000)
    cutoff = now_ms - window_ms
    rkey = f"rl:{key}"
    try:
        p = cli.pipeline()
        p.zremrangebyscore(rkey, 0, cutoff)
        p.zcard(rkey)
        _cleaned, count = p.execute()
        if count >= max_requests:
            # Compute retry-after from oldest remaining entry
            oldest = cli.zrange(rkey, 0, 0, withscores=True)
            retry_after = 1
            if oldest:
                retry_after = max(1, int((oldest[0][1] + window_ms - now_ms) / 1000) + 1)
            raise HTTPException(
                status_code=429,
                detail="Too many requests — try again shortly",
                headers={"Retry-After": str(retry_after)},
            )
        # Record hit — use a unique member so parallel same-ms hits don't collide
        member = f"{now_ms}-{os.urandom(4).hex()}"
        p = cli.pipeline()
        p.zadd(rkey, {member: now_ms})
        p.expire(rkey, int(window_secs) + 1)
        p.execute()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — Redis flaked mid-call
        logger.warning("Redis rate-limit call failed (%s) — degrading to memory", exc)
        _check_in_memory(key, max_requests, window_secs)


def check(key: str, *, max_requests: int, window_secs: float = 60.0) -> None:
    """Raise HTTP 429 if `key` has exceeded `max_requests` in the last
    `window_secs`. Uses Redis when available, otherwise in-memory."""
    cli = _get_redis()
    if cli is None:
        _check_in_memory(key, max_requests, window_secs)
    else:
        _check_redis(cli, key, max_requests, window_secs)


def backend() -> str:
    """Introspection helper — returns 'redis' or 'memory'."""
    return "redis" if _get_redis() is not None else "memory"


def reset(key: Optional[str] = None) -> None:
    """Test helper — clear a specific key or everything."""
    cli = _get_redis()
    if cli is not None:
        if key:
            cli.delete(f"rl:{key}")
        else:
            for k in cli.scan_iter("rl:*"):
                cli.delete(k)
    with _mem_lock:
        if key:
            _mem_buckets.pop(key, None)
        else:
            _mem_buckets.clear()
