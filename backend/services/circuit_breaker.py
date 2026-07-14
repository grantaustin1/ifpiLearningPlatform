"""Iter 38 Phase C — Circuit breaker for expensive external work.

Use case: certificate PDF generation. Under load, the WeasyPrint /
Playwright PDF stack can wedge (memory pressure, font-loading stalls).
Without a breaker, a wedged renderer serializes the entire enrollment
flow behind it.

Design: classic 3-state breaker (CLOSED → OPEN → HALF_OPEN).
- **CLOSED** — calls flow through. Consecutive failures within the
  window accumulate.
- **OPEN** — calls fail fast with a defined fallback for `reset_after`
  seconds. Learner sees "certificate queued for later" instead of a
  500.
- **HALF_OPEN** — after `reset_after`, one probe call is allowed. If
  it succeeds, breaker CLOSES. If it fails, back to OPEN for another
  window.

Zero deps. Per-name instances so certificate rendering has its own
breaker separate from other subsystems.
"""
from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when a call is short-circuited because the breaker is OPEN."""


class CircuitBreaker:
    def __init__(self, *, name: str,
                 failure_threshold: int = 5,
                 reset_after_seconds: float = 30.0) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_after_seconds = reset_after_seconds
        self._state = "closed"  # closed | open | half_open
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = Lock()

    def _try_transition_from_open(self) -> None:
        """If enough time has passed since we opened, move to HALF_OPEN
        for a probe call."""
        if self._state == "open" and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.reset_after_seconds:
                self._state = "half_open"
                logger.info("[cb:%s] transitioning open → half_open", self.name)

    def call(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """Run `fn` through the breaker. Raises `CircuitBreakerOpen`
        if the breaker is open. On failure, records and re-raises the
        original exception."""
        with self._lock:
            self._try_transition_from_open()
            if self._state == "open":
                raise CircuitBreakerOpen(
                    f"Breaker {self.name!r} is OPEN — call rejected. "
                    f"Retry in ~{self.reset_after_seconds:.0f}s."
                )
        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._on_failure()
            raise
        with self._lock:
            self._on_success()
        return result

    def _on_success(self) -> None:
        if self._state == "half_open":
            logger.info("[cb:%s] probe succeeded, closing breaker", self.name)
        self._state = "closed"
        self._failures = 0
        self._opened_at = None

    def _on_failure(self) -> None:
        self._failures += 1
        if self._state == "half_open":
            # Probe failed — back to OPEN for another cooldown
            self._state = "open"
            self._opened_at = time.monotonic()
            logger.warning("[cb:%s] probe failed, re-opening breaker", self.name)
            return
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
            logger.warning(
                "[cb:%s] opening breaker — %d consecutive failures",
                self.name, self._failures,
            )

    def snapshot(self) -> dict:
        with self._lock:
            self._try_transition_from_open()
            return {
                "name": self.name,
                "state": self._state,
                "failures": self._failures,
                "opened_at": self._opened_at,
                "reset_after_seconds": self.reset_after_seconds,
            }


# Named singletons — accessed via `get_breaker(name)`.
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = Lock()


def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    with _breakers_lock:
        cb = _breakers.get(name)
        if cb is None:
            cb = _breakers[name] = CircuitBreaker(name=name, **kwargs)
        return cb


# Well-known breaker for certificate PDF generation.
def cert_generation_breaker() -> CircuitBreaker:
    return get_breaker("cert_pdf_generation",
                       failure_threshold=5,
                       reset_after_seconds=30.0)
