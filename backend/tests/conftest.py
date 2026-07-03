"""Test-suite configuration.

All backend tests in this folder are *integration* tests — they hit a
running IFPI backend over HTTP. In CI (GitHub Actions etc.) that backend
is usually not running, so we auto-skip the whole suite unless a live
backend is reachable at REACT_APP_BACKEND_URL.

Local dev: supervisor runs the backend + preview URL is set in
`/app/frontend/.env`. The conftest picks it up and tests run normally.

CI override: set `RUN_INTEGRATION_TESTS=1` to force execution regardless
(useful when a dedicated CI job spins up a backend container first).
"""
from __future__ import annotations

import os
import socket
import urllib.parse

import pytest


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if url:
        return url
    # Fallback: read /app/frontend/.env when running from /app/backend
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    val = line.split("=", 1)[1].strip().rstrip("/")
                    if val:
                        os.environ["REACT_APP_BACKEND_URL"] = val
                        return val
    except FileNotFoundError:
        pass
    return ""


def _reachable(url: str, timeout: float = 2.0) -> bool:
    """Quick TCP probe. HTTP/HTTPS agnostic — we only care that *something*
    listens on the resolved host:port."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


BACKEND_URL = _load_backend_url()
FORCE_RUN = os.environ.get("RUN_INTEGRATION_TESTS") == "1"
_BACKEND_LIVE = bool(BACKEND_URL) and _reachable(BACKEND_URL)


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when the backend is unreachable and the
    operator hasn't explicitly opted in with RUN_INTEGRATION_TESTS=1.

    Static tests (docs completeness, import checks) never touch the
    backend, so they always run — even without a live server."""
    if FORCE_RUN or _BACKEND_LIVE:
        return
    reason = (
        "IFPI backend not reachable at "
        f"{BACKEND_URL or '<unset>'} — integration tests skipped. "
        "Set RUN_INTEGRATION_TESTS=1 to force."
    )
    skip = pytest.mark.skip(reason=reason)
    static_prefixes = ("test_docs_", "test_static_", "test_lint_")
    for item in items:
        module_name = item.nodeid.split("::", 1)[0].split("/")[-1]
        if any(module_name.startswith(p) for p in static_prefixes):
            continue  # static tests always run
        item.add_marker(skip)
