"""Dedicated worker pool for long-running blocking AI calls (Iter 28).

FastAPI's `BackgroundTasks` runs sync callables on the shared anyio thread
pool. When a Sora 2 job blocks for 3-5 minutes, it holds a slot the same
pool needs for every other sync route handler — under load, unrelated
endpoints time out.

This module hosts a dedicated `ThreadPoolExecutor` (default 2 workers) that
Sora + any future long-running blocker submits to. Workers here NEVER
serve HTTP requests, so a stuck Sora call can't cascade.

Usage:
    from services.background_worker import submit_long_job
    submit_long_job(_run_video_job, job_id, org_id, ...)
"""
from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger("ifpi.worker")

# 2 concurrent Sora renders is a reasonable ceiling — pushes back on cost
# runaway and matches the OpenAI account's typical Sora concurrency limit.
_MAX_LONG_WORKERS = 2

_pool: ThreadPoolExecutor | None = None


def _get_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(
            max_workers=_MAX_LONG_WORKERS,
            thread_name_prefix="ifpi-long-worker",
        )
        logger.info("Long-job worker pool started (workers=%d)", _MAX_LONG_WORKERS)
    return _pool


def submit_long_job(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    """Submit a blocking job onto the dedicated long-worker pool. Returns
    the concurrent.futures.Future — callers can ignore it (fire-and-forget)
    or await result() from a helper.
    """
    fut = _get_pool().submit(fn, *args, **kwargs)

    def _log(f: Future) -> None:
        exc = f.exception()
        if exc is not None:
            logger.exception("Long-job crashed: %s", exc)

    fut.add_done_callback(_log)
    return fut


def shutdown_long_workers(wait: bool = False) -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=wait, cancel_futures=not wait)
        _pool = None
