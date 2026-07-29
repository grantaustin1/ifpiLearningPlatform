"""Lint: every FastAPI endpoint's type hints must resolve at import time.

Catches the class of bug where a decorator + `from __future__ import
annotations` leaves an annotation as an unresolved `ForwardRef` — which
FastAPI then treats as a query parameter, silently 422-ing every request
to that endpoint.

Concrete example this catches (broken in CI before Iter 39 fix):

    # services/db_locks.py — decorator module, missing Request import
    def retry_on_deadlock():
        def _decorator(fn):
            @functools.wraps(fn)
            def _wrapped(*a, **kw): return fn(*a, **kw)
            return _wrapped

    # routers/courses.py — endpoint module, has Request import
    from __future__ import annotations
    from fastapi import Request

    @router.post("/{course_id}/complete")
    @retry_on_deadlock()
    def complete(course_id: int, request: Request): ...

`get_type_hints(complete)` walks the wrapper's __globals__ (db_locks)
which doesn't have Request → annotation stays a ForwardRef →
FastAPI 422s the endpoint.

Run: `python /app/backend/scripts/lint_endpoint_signatures.py`
Exit codes: 0 = clean, 1 = one or more endpoints have unresolved hints.
"""
from __future__ import annotations

import sys
import typing
from pathlib import Path
from typing import get_type_hints

# Ensure the backend package is importable regardless of the caller's cwd.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _run() -> int:
    # Import the app WITHOUT starting supervisor / servers. This uses
    # the same import path production uses so we catch real breakage.
    from server import app  # noqa: WPS433 — import lives here to fail fast

    problems: list[str] = []
    checked = 0

    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        # Only interested in real API routes with an inspectable callable.
        try:
            hints = get_type_hints(endpoint)
        except Exception as e:  # noqa: BLE001
            problems.append(
                f"  ✗ {route.path!r} {endpoint.__module__}.{endpoint.__name__} "
                f"— get_type_hints raised: {type(e).__name__}: {e}"
            )
            continue
        checked += 1

        for name, hint in hints.items():
            # A resolved hint is a class / typing construct; an
            # unresolved one is a ForwardRef instance.
            if isinstance(hint, typing.ForwardRef):
                problems.append(
                    f"  ✗ {route.path!r} — param {name!r} annotation "
                    f"is an unresolved ForwardRef({hint.__forward_arg__!r}). "
                    f"Endpoint: {endpoint.__module__}.{endpoint.__name__}. "
                    f"Common cause: a decorator whose wrapper module "
                    f"doesn't import the annotation's type."
                )

    print(f"Checked {checked} endpoints.")
    if problems:
        print("\nUnresolved endpoint annotations (would cause 422s at request time):\n")
        for line in problems:
            print(line)
        print(
            "\nFix: import the type in the decorator's module so "
            "`get_type_hints(wrapper)` can resolve it via "
            "`wrapper.__globals__`. Example (services/db_locks.py):\n\n"
            "    from fastapi import Request  # noqa: F401\n"
        )
        return 1
    print("✅  All endpoint annotations resolve cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
