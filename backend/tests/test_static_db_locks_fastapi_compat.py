"""Tests for the FastAPI annotation-resolution fix in retry_on_deadlock.

When a route handler module uses ``from __future__ import annotations``
all annotations are stored as strings.  FastAPI's ``get_typed_signature``
resolves those strings against ``_wrapped.__globals__`` (the decorator
module's namespace), not the original function's globals.  Types such as
``Request`` and ``CurrentUser`` that are not imported in ``db_locks.py``
would remain as unresolved ``ForwardRef``s and be treated as required
query/body parameters, causing a 422 on every matching request.

The fix in :func:`services.db_locks.retry_on_deadlock` injects type-class
annotations from the original function's globals into the wrapper's
globals.  These tests lock in that behaviour.
"""
from __future__ import annotations

import types as _types

import pytest


# ── helpers ───────────────────────────────────────────────────────────

def _make_wrapped_in_own_module(source: str):
    """Compile *source* as a fresh module and return its ``app`` attribute."""
    code = compile(source, "<test_module>", "exec")
    globs = {
        "__name__": "test_module",
        "__file__": "<test_module>",
        "__builtins__": __builtins__,
    }
    exec(code, globs)  # noqa: S102
    return globs["app"]


# ── unit-level tests (no FastAPI server needed) ───────────────────────

class TestRetryOnDeadlockAnnotationInjection:
    """Verify that annotation types are (or are not) injected into the
    wrapper's ``__globals__`` after decoration."""

    def test_class_annotation_injected_into_wrapper_globals(self):
        """A class used as a type annotation in the original function is
        injected into _wrapped.__globals__ so FastAPI can resolve it."""
        import sys
        import importlib
        sys.path.insert(0, ".")

        from services.db_locks import retry_on_deadlock

        class _MyType:
            pass

        # Define a function whose module globals contain _MyType
        def _fn(x: "_MyType") -> None:  # noqa: F821 – string annotation
            pass

        _fn.__annotations__ = {"x": "_MyType"}
        _fn.__globals__["_MyType"] = _MyType  # inject into callee globals

        wrapped = retry_on_deadlock()(_fn)
        assert "_MyType" in wrapped.__globals__
        assert wrapped.__globals__["_MyType"] is _MyType

    def test_non_class_value_not_injected(self):
        """A module-level non-class object (e.g. a constant string) whose
        name happens to match an annotation string must NOT be injected."""
        from services.db_locks import retry_on_deadlock

        def _fn(x: "_NOT_A_CLASS") -> None:
            pass

        _fn.__annotations__ = {"x": "_NOT_A_CLASS"}
        # Simulate a non-class value in the caller's globals
        _fn.__globals__["_NOT_A_CLASS"] = "just a string, not a type"

        wrapped = retry_on_deadlock()(_fn)
        assert "_NOT_A_CLASS" not in wrapped.__globals__

    def test_existing_global_not_overwritten(self):
        """Names already present in the wrapper's globals must not be
        overwritten (setdefault semantics)."""
        from services.db_locks import retry_on_deadlock

        class _Sentinel:
            pass

        class _Original:
            pass

        def _fn(x: "Session") -> None:
            pass

        _fn.__annotations__ = {"x": "Session"}

        # Put a *different* object into the caller's globals
        _fn.__globals__["Session"] = _Original

        # Put the *original* sentinel in db_locks globals via a temporary wrap
        from services import db_locks as _dl
        original_session = _dl.__dict__.get("Session", _Sentinel)

        wrapped = retry_on_deadlock()(_fn)

        # db_locks already imports Session from SQLAlchemy; the caller's
        # version must not replace it.
        assert wrapped.__globals__["Session"] is original_session


# ── FastAPI integration test (lightweight, no running server) ─────────

class TestRetryOnDeadlockFastAPIRequest:
    """Verify that FastAPI treats ``request: Request`` as an auto-injected
    parameter (not a required query/body field) when the handler is
    decorated with ``@retry_on_deadlock()``."""

    def test_request_param_not_treated_as_query_field(self):
        """POST /{course_id}/complete must return 200, not 422, when
        the handler uses ``request: Request`` and ``@retry_on_deadlock()``
        with ``from __future__ import annotations`` active in the handler
        module."""
        import sys
        sys.path.insert(
            0, str(
                __import__("pathlib").Path(__file__).resolve().parents[1]
            )
        )
        from fastapi.testclient import TestClient

        source = """
from __future__ import annotations
from fastapi import FastAPI, Request
from services.db_locks import retry_on_deadlock

app = FastAPI()

@app.post("/test/{course_id}/complete")
@retry_on_deadlock()
def complete_course(course_id: int, request: Request):
    return {"ok": True, "course_id": course_id}
"""
        app = _make_wrapped_in_own_module(source)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test/42/complete")
        assert resp.status_code == 200, (
            f"Expected 200 but got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body["ok"] is True
        assert body["course_id"] == 42

    def test_without_decorator_422_is_avoided(self):
        """Baseline: without the decorator the endpoint still returns 200."""
        from fastapi.testclient import TestClient

        source = """
from __future__ import annotations
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/test/{course_id}/enroll")
def enroll(course_id: int):
    return {"ok": True, "course_id": course_id}
"""
        app = _make_wrapped_in_own_module(source)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test/7/enroll")
        assert resp.status_code == 200
