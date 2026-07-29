"""Regression: `@retry_on_deadlock` + `from __future__ import annotations`
+ `request: Request` param no longer 422s.

Root cause: FastAPI's `get_type_hints(endpoint)` uses the wrapper
function's `__globals__` to resolve string annotations. Without the
`Request` name being in scope in `services.db_locks`, FastAPI treats
`request` as a query parameter and returns 422 with
`{loc: ["query", "request"], type: "missing"}`.

Fix: import `Request` at module scope in `services.db_locks` (see the
`# noqa: F401` re-export block there).

Regression surface: this bug broke `POST /api/courses/{id}/complete`
end-to-end, taking down the QA agent 008 E2E learner journey in CI.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

from tests.conftest import authed_session


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestCompleteCourseEndpoint:
    def test_complete_returns_200_not_422(self):
        """Full HTTP round-trip. Uses the shared learner account; the
        endpoint is idempotent so the second run just returns
        `already_completed: True` — either shape is acceptable, we
        only care that it's NOT a 422."""
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(f"{BASE_URL}/api/courses/1/complete", timeout=10)
        assert r.status_code == 200, (
            f"expected 200, got {r.status_code} with body {r.text[:200]}"
        )
        body = r.json()
        assert "ok" in body

    def test_complete_v1_alias_also_works(self):
        s = authed_session("learner@ifpi.org", "learner123", BASE_URL)
        r = s.post(f"{BASE_URL}/api/v1/courses/1/complete", timeout=10)
        assert r.status_code == 200, r.text
        assert r.headers.get("X-API-Version") == "v1"


class TestDecoratorSignatureIntrospection:
    """Unit-level guard: FastAPI's `get_type_hints` on a decorated
    endpoint must resolve `Request` to the actual class, not leave it
    as an unresolved `ForwardRef`."""

    def test_get_type_hints_resolves_request_annotation(self):
        from fastapi import Request
        from fastapi.dependencies.utils import get_typed_signature
        from services.db_locks import retry_on_deadlock

        @retry_on_deadlock()
        def endpoint(course_id: int, request: Request):
            pass

        sig = get_typed_signature(endpoint)
        req_param = sig.parameters["request"]
        # It must be the actual class, not a ForwardRef string.
        assert req_param.annotation is Request, (
            f"Expected annotation to resolve to Request class, "
            f"got {req_param.annotation!r}. This means "
            f"`from __future__ import annotations` + the retry wrapper "
            f"lost the type context."
        )
