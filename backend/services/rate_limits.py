"""Inline sliding-window rate limiter for high-fanout inbound routes.

Purpose: cap how fast a single ERP360 signing key (or client IP,
fallback) can hammer our webhook receiver. Under a stampede — bad
retry loop on the caller side, misconfigured k6 script, malicious
replay — this returns `429 Too Many Requests` fast, without holding
worker threads on signature verification and DB writes.

Design notes:
  - Sliding-window counter in a bounded LRU dict. No new deps.
  - Keyed on a caller-provided string (typically the last 8 chars of
    `X-ERP360-Signature` — enough entropy to distinguish trusted keys
    without leaking the full HMAC in logs). Falls back to client IP.
  - Multi-worker safety: this is per-process. Good enough for our
    single-pod deploy target. If we scale to multiple pods, swap the
    backing dict for Redis (2-line change — keep the same interface).
  - Zero-cost fast path: dict lookup + append + prune. ~1µs per call.

Rate is a soft protection layer — signature verification is still
the hard security gate.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Deque, Dict


class SlidingWindowLimiter:
    """Per-key sliding window. Bounded memory via LRU eviction."""

    def __init__(self, *, limit: int, window_seconds: float,
                 max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._buckets: Dict[str, Deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return `(allowed, remaining)`. Increments the counter on
        allowed calls."""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self.max_keys:
                    # Evict the oldest bucket — coarse but safe. In
                    # practice we should never hit this from real
                    # traffic (10k distinct HMAC keys is a lot).
                    self._buckets.pop(next(iter(self._buckets)), None)
                bucket = self._buckets[key] = deque()
            # Prune expired entries from the front
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False, 0
            bucket.append(now)
            return True, self.limit - len(bucket)


# Webhook receiver: 200 req/min per signing-key prefix. Comfortably
# above ERP360's own retry budget (3 attempts over 15 min for the same
# event; unrelated events dispatched from ERP360 admin edits are the
# realistic load). At 10× the expected steady-state this still leaves
# generous headroom.
erp360_webhook_limiter = SlidingWindowLimiter(limit=200, window_seconds=60.0)
