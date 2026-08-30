"""Tiny pluggable TTL cache.

In-process by default (zero infrastructure); switches to Redis automatically
when REDIS_URL is set, so the same call sites scale horizontally later.
Values must be pickleable. Payloads are HMAC-signed (key derived from
JWT_SECRET) and verified before unpickling, so a compromised Redis can't
smuggle a pickle-RCE payload into the app. Never cache anything
correctness-critical (learner progress, entitlements) — only read-heavy
aggregates + auth lookups with short TTLs and explicit invalidation on writes.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import pickle
import threading
import time
from typing import Any, Callable, Optional

_REDIS_URL = os.environ.get("REDIS_URL", "").strip()


class _MemoryBackend:
    def __init__(self):
        self._data: dict[str, tuple[float, bytes]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, blob = item
            if expires < time.time():
                del self._data[key]
                return None
            return blob

    def set(self, key: str, blob: bytes, ttl: int) -> None:
        with self._lock:
            # opportunistic sweep to bound memory
            if len(self._data) > 5000:
                now = time.time()
                for k in [k for k, (exp, _) in self._data.items() if exp < now]:
                    del self._data[k]
            self._data[key] = (time.time() + ttl, blob)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            for k in [k for k in self._data if k.startswith(prefix)]:
                del self._data[k]


class _RedisBackend:
    def __init__(self, url: str):
        import redis
        self._r = redis.Redis.from_url(url)

    def get(self, key: str) -> Optional[bytes]:
        try:
            return self._r.get(key)
        except Exception:
            return None  # cache must never take the app down

    def set(self, key: str, blob: bytes, ttl: int) -> None:
        try:
            self._r.setex(key, ttl, blob)
        except Exception:
            pass

    def delete(self, key: str) -> None:
        try:
            self._r.delete(key)
        except Exception:
            pass

    def invalidate_prefix(self, prefix: str) -> None:
        try:
            for k in self._r.scan_iter(match=prefix + "*", count=500):
                self._r.delete(k)
        except Exception:
            pass


_backend = _RedisBackend(_REDIS_URL) if _REDIS_URL else _MemoryBackend()

# ── Signed serialization — defends against pickle RCE if the cache
# store (Redis) is ever compromised. Blob layout: 32-byte HMAC-SHA256
# digest || pickle payload. Verification failure = cache miss.
_SIG_LEN = 32


def _sign_key() -> bytes:
    from core.config import settings
    return hashlib.sha256(f"cache-sign:{settings.jwt_secret}".encode()).digest()


def _serialize(value: Any) -> bytes:
    payload = pickle.dumps(value)
    sig = hmac.new(_sign_key(), payload, hashlib.sha256).digest()
    return sig + payload


def _deserialize(blob: bytes) -> Any:
    if len(blob) <= _SIG_LEN:
        return None
    sig, payload = blob[:_SIG_LEN], blob[_SIG_LEN:]
    expected = hmac.new(_sign_key(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None  # tampered or legacy-format entry — treat as miss
    return pickle.loads(payload)


def cache_get(key: str) -> Any:
    blob = _backend.get(key)
    return _deserialize(blob) if blob is not None else None


def cache_set(key: str, value: Any, ttl: int) -> None:
    _backend.set(key, _serialize(value), ttl)


def cache_delete(key: str) -> None:
    _backend.delete(key)


def invalidate(prefix: str) -> None:
    _backend.invalidate_prefix(prefix)


def cached(key: str, ttl: int, producer: Callable[[], Any]) -> Any:
    """Read-through helper: return cached value or produce + store it."""
    hit = cache_get(key)
    if hit is not None:
        return hit
    value = producer()
    if value is not None:
        cache_set(key, value, ttl)
    return value
