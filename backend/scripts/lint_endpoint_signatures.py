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

Two lint passes:

  1. **Endpoint pass** (default) — walks `app.routes`, runs
     `get_type_hints` on each endpoint. Catches actual leaks after
     decorators have been attached.

  2. **Decorator pass** (`--check-decorators`) — walks every decorator
     module under `services/` and `core/`, checks if it defines a
     `functools.wraps`-based wrapper WITHOUT importing the common
     FastAPI annotation types (`Request`, `Response`, `BackgroundTasks`).
     ADVISORY: prints a warning but doesn't fail the build. Catches
     the bug at DEFINITION time, before a caller ever attaches the
     decorator to an endpoint.

Run:
    python /app/backend/scripts/lint_endpoint_signatures.py
    python /app/backend/scripts/lint_endpoint_signatures.py --check-decorators

Exit codes: 0 = clean, 1 = one or more endpoints have unresolved hints.
"""
from __future__ import annotations

import ast
import sys
import typing
from pathlib import Path
from typing import get_type_hints

# Ensure the backend package is importable regardless of the caller's cwd.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# Types most likely to be annotated on FastAPI endpoints. When a
# decorator module (services/*.py, core/*.py) wraps endpoints, its
# __globals__ must contain these names so `get_type_hints(wrapper)`
# can resolve `request: Request`, `response: Response`, etc.
_EXPECTED_ANNOTATION_IMPORTS = {"Request", "Response", "BackgroundTasks"}


def _check_decorator_modules() -> int:
    """Advisory pass: scan every module under `services/` and `core/`.
    If a module defines a `functools.wraps`-based decorator but its
    top-level imports omit the common FastAPI annotation types, print
    an ADVISORY WARNING. Does NOT fail the build — many decorators
    legitimately don't wrap FastAPI endpoints (e.g. pure worker
    decorators). But every WARNING is worth reading before you attach
    the decorator to an endpoint that annotates one of those types.
    """
    scan_dirs = [_BACKEND_DIR / "services", _BACKEND_DIR / "core"]
    warnings: list[str] = []
    checked = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in sorted(scan_dir.rglob("*.py")):
            if py_file.name.startswith("_") or py_file.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            # Detect `functools.wraps` usage — heuristic for "this
            # module defines a decorator that wraps another function".
            has_functools_wraps = False
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "functools"
                        and node.attr == "wraps"):
                    has_functools_wraps = True
                    break

            if not has_functools_wraps:
                continue
            checked += 1

            # Collect top-level names imported into the module.
            imported_names: set[str] = set()
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names.add(alias.asname
                                           or alias.name.split(".")[0])

            missing = _EXPECTED_ANNOTATION_IMPORTS - imported_names
            if missing == _EXPECTED_ANNOTATION_IMPORTS:
                # Missing ALL of them — probably not a FastAPI-endpoint
                # wrapper. Skip to keep the signal-to-noise high.
                continue
            if missing:
                rel = py_file.relative_to(_BACKEND_DIR)
                warnings.append(
                    f"  ⚠️  {rel} defines a functools.wraps decorator but "
                    f"does not import {sorted(missing)!r} at module scope. "
                    f"If any endpoint annotated with one of those types is "
                    f"decorated with this wrapper, "
                    f"`get_type_hints(endpoint)` will leak a ForwardRef "
                    f"and FastAPI will 422 the endpoint."
                )

    print(f"Decorator-pass: checked {checked} modules with "
          f"`functools.wraps`.")
    if warnings:
        print("\nAdvisory warnings (not build-failing):\n")
        for line in warnings:
            print(line)
        print(
            "\nFix: add `# noqa: F401` re-exports at module scope, e.g.:\n\n"
            "    from fastapi import Request, Response  # noqa: F401\n"
        )
    else:
        print("✅  No decorator modules missing expected annotation imports.")
    # Advisory only — never fail the build.
    return 0


def _run() -> int:
    check_decorators = "--check-decorators" in sys.argv[1:]

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

    print(f"Endpoint pass: checked {checked} endpoints.")
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

    if check_decorators:
        print()
        _check_decorator_modules()

    return 0


if __name__ == "__main__":
    sys.exit(_run())
