"""Locks in the fix for the `POST /api/courses/{id}/complete` 422
regression (Iter 39 CI fix).

Two invariants:

1. The `lint_endpoint_signatures.py` script exists and exits 0 on
   the live app. This is the primary guard — any future decorator
   that leaks a ForwardRef will fail it.

2. Any module that defines a decorator used on FastAPI endpoints
   MUST import the types those endpoints annotate (e.g. `Request`,
   `Response`). We codify this by asserting `services.db_locks`
   (which wraps `POST /courses/{id}/complete`) has `Request` in its
   module namespace. Same for `services.cache`.

Missing this test guarantees the bug can silently return.
"""
from __future__ import annotations

import subprocess


def test_lint_endpoint_signatures_passes():
    """The live app must have zero ForwardRef leaks on any endpoint."""
    r = subprocess.run(
        ["python", "/app/backend/scripts/lint_endpoint_signatures.py"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, (
        f"lint_endpoint_signatures failed with exit {r.returncode}.\n"
        f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
    assert "All endpoint annotations resolve cleanly" in r.stdout


def test_db_locks_module_re_exports_request():
    """`services.db_locks` wraps endpoints with `request: Request`.
    Its `__globals__` MUST contain `Request` so FastAPI's
    `get_type_hints(wrapper)` can resolve the annotation.

    If this assertion ever fires, remove ONLY the re-export block in
    db_locks.py at your peril — the annotation will leak as a
    ForwardRef and every `@retry_on_deadlock`-decorated endpoint
    with a `Request` param will silently 422.
    """
    from services import db_locks
    assert hasattr(db_locks, "Request"), (
        "services.db_locks must re-export `Request` at module scope. "
        "See the noqa: F401 block near the top of db_locks.py — "
        "removing it breaks POST /api/courses/{id}/complete."
    )


def test_cache_module_re_exports_request_and_response():
    """Same requirement for `services.cache` — its `@cached_view`
    decorator wraps endpoints that annotate `response: Response`
    (and could annotate Request in future)."""
    from services import cache
    assert hasattr(cache, "Response"), (
        "services.cache must re-export `Response` at module scope."
    )
    assert hasattr(cache, "Request"), (
        "services.cache must re-export `Request` at module scope."
    )
