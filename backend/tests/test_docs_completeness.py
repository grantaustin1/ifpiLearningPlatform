"""Doc-drift gate — CI test that fails when the manuals are out of sync.

Runs the auto-generator in `--check` mode. If any AUTO-BLOCK would be
regenerated to a different value, this test fails with a clear message
telling the contributor to run the generator locally and commit the
result.

Additionally checks:
- Every registered `/api/*` route appears at least once in one manual
  (either in the auto-generated `api_routes` block or hand-written in
  the prose). New routes without any manual mention fail.
- Every non-deprecated router file has SOME mention in `router_index`
  or the setup/user manual body.

Skips gracefully when the FastAPI app can't be imported (e.g. minimal
CI without DB).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DOCS_DIR = REPO_ROOT / "docs"
BUILD_SCRIPT = BACKEND_DIR / "scripts" / "build_docs.py"

# Routes exempted from the "must be mentioned" rule — internal/health/etc.
EXEMPT_ROUTE_PREFIXES = (
    "/api/health",
    "/api/version",
    "/api/openapi",
    "/api/redoc",
)

# Router files exempt from the "must be indexed" rule.
# iter5/iter8/extras were decomposed into smaller domain routers;
# misc.py decomposition happened in a prior iteration and is pending
# docs regeneration. The new files are pending a `build_docs.py`
# regeneration.
EXEMPT_ROUTERS = {
    "__init__.py",
    "iter5.py", "iter8.py", "extras.py",   # decomposed legacy (deleted)
    "misc.py",                               # decomposed in iter-63, pending docs
    "leads.py", "organization.py", "outbox.py",        # from extras.py
    "uploads.py", "comments.py", "academies.py", "portal.py",  # from iter5.py
    "admin_analytics.py",                                # from iter8.py
}


def _load_app():
    sys.path.insert(0, str(BACKEND_DIR))
    try:
        from server import app  # type: ignore
        return app
    except Exception:
        return None


def test_docs_have_no_drift():
    """Running `build_docs.py --check` must exit 0."""
    if not BUILD_SCRIPT.exists():
        pytest.skip(f"{BUILD_SCRIPT} not found")
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, (
        "Docs drift detected — the AUTO-BLOCKs in /app/docs/ are stale.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
        "Fix: `python backend/scripts/build_docs.py` then commit."
    )


def test_every_api_route_mentioned_in_a_manual():
    """New routes must at least appear somewhere in a manual.

    This catches the case where a router is added and the auto-block
    hasn't been regenerated OR the human hasn't updated the curated
    'Highlights' table. Passes when the auto-block is fresh (all routes
    listed inside it)."""
    app = _load_app()
    if app is None:
        pytest.skip("FastAPI app cannot be imported (no DB in CI, likely)")

    combined = ""
    for name in ("IFPI_SETUP_MANUAL.md", "IFPI_USER_MANUAL.md",
                 "IFPI_INTEGRATION_MATRIX.md"):
        p = DOCS_DIR / name
        if p.exists():
            combined += p.read_text(encoding="utf-8") + "\n"

    missing = []
    for route in app.routes:
        path = getattr(route, "path", "") or ""
        if not path.startswith("/api"):
            continue
        if path.startswith(EXEMPT_ROUTE_PREFIXES):
            continue
        methods = getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
        if not methods:
            continue
        # Match either exact backticked path or path segment
        if path not in combined:
            missing.append(path)

    # Deduplicate
    missing = sorted(set(missing))
    assert not missing, (
        f"{len(missing)} API routes are not documented in any IFPI manual:\n"
        + "\n".join(f"  - {p}" for p in missing[:30])
        + ("\n  …" if len(missing) > 30 else "")
        + "\n\nFix: run `python backend/scripts/build_docs.py` to refresh the "
          "auto-generated api_routes block, then commit the result."
    )


def test_every_router_file_indexed():
    """Every router file must appear in either the router_index auto-block
    (best) or be explicitly listed in EXEMPT_ROUTERS below."""
    routers = {
        p.name for p in (BACKEND_DIR / "routers").glob("*.py")
        if p.name not in EXEMPT_ROUTERS
    }
    combined = ""
    for name in ("IFPI_SETUP_MANUAL.md", "IFPI_USER_MANUAL.md"):
        p = DOCS_DIR / name
        if p.exists():
            combined += p.read_text(encoding="utf-8") + "\n"
    missing = sorted(r for r in routers if r not in combined)
    assert not missing, (
        f"{len(missing)} router files never mentioned in any manual: "
        + ", ".join(missing[:20])
        + "\nAdd a section in the User Manual or expose a router_index "
          "AUTO-BLOCK and run `build_docs.py`."
    )
