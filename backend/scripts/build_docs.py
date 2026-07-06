"""IFPI Manual Auto-Regenerator (mirrors ERP360's build_tenant_setup_guide_v2.py pattern).

Scans the live FastAPI app + role_registry and rewrites the AUTO-BLOCK
sections inside `/app/docs/IFPI_*_MANUAL.md`. Human-written prose OUTSIDE
those markers is untouched.

Usage:
    python backend/scripts/build_docs.py            # regenerate
    python backend/scripts/build_docs.py --check    # exit 1 if regen would change files (CI drift gate)
    python backend/scripts/build_docs.py --html     # also emit HTML render

Auto-blocks recognised (referenced by name inside `<!-- AUTO:BEGIN X --> ... <!-- AUTO:END X -->`):
    role_matrix       — canonical role table from core/role_registry.py
    role_aliases      — role aliases from core/role_registry.py
    api_routes        — every registered route with verb + path + summary
    router_index      — inventory of routers/*.py with line counts
    model_index       — inventory of models/*.py

Design notes:
- We do NOT re-render the whole file — just the blocks. This means
  writers can add/edit prose freely without fighting the generator.
- Every regenerated block is idempotent: `regen | regen == regen`.
- The `--check` mode is what CI runs. Non-zero exit means somebody
  merged code without regenerating docs.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

MANUAL_FILES = [
    DOCS_DIR / "IFPI_SETUP_MANUAL.md",
    DOCS_DIR / "IFPI_USER_MANUAL.md",
    DOCS_DIR / "IFPI_INTEGRATION_MATRIX.md",
    DOCS_DIR / "IFPI_VS_ERP360_ASSESSMENT.md",
]

BLOCK_RE = re.compile(
    r"<!-- AUTO:BEGIN (\w+) -->.*?<!-- AUTO:END \1 -->",
    re.DOTALL,
)


# ─────────────────────────────────────────────────────────────────────
# Block generators — each returns the *inner* markdown between markers
# ─────────────────────────────────────────────────────────────────────


def _gen_role_matrix() -> str:
    from core.role_registry import CANONICAL_ROLE_REGISTRY

    lines = ["| Role | Description |", "|---|---|"]
    for role, desc in CANONICAL_ROLE_REGISTRY.items():
        lines.append(f"| `{role}` | {desc} |")
    return "\n".join(lines)


def _gen_role_aliases() -> str:
    from core.role_registry import ROLE_ALIAS_TO_CANONICAL

    lines = ["| Alias | Canonical |", "|---|---|"]
    for alias, canonical in ROLE_ALIAS_TO_CANONICAL.items():
        lines.append(f"| `{alias}` | `{canonical}` |")
    return "\n".join(lines)


def _load_app():
    """Import the FastAPI app for route introspection. May fail in CI
    without a DB — we return None and the caller falls back to a stub."""
    try:
        from server import app  # type: ignore
        return app
    except Exception as exc:  # noqa: BLE001
        print(f"[build_docs] app import failed ({exc!r}); "
              "route table will be a stub", file=sys.stderr)
        return None


def _summarize_route(route) -> Tuple[str, str, str]:
    path = getattr(route, "path", "")
    methods = sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"})
    verb = "/".join(methods) if methods else ""
    summary = (getattr(route, "summary", "") or "").strip()
    if not summary:
        # Fallback: first docstring line
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None and endpoint.__doc__:
            summary = endpoint.__doc__.strip().splitlines()[0].strip()
    return verb, path, summary


def _collect_routes(router_or_app) -> List:
    """Recursively collect all route objects from a FastAPI app or router.

    FastAPI ≥ 0.139 stores included routers as ``_IncludedRouter``
    wrappers rather than immediately flattening them into the parent's
    ``routes`` list.  We unwrap those transparently so route introspection
    works correctly regardless of FastAPI version.
    """
    from fastapi.routing import APIRoute
    collected = []
    for r in getattr(router_or_app, "routes", []):
        if isinstance(r, APIRoute):
            collected.append(r)
        elif hasattr(r, "original_router"):
            # FastAPI 0.139+ _IncludedRouter
            collected.extend(_collect_routes(r.original_router))
        elif hasattr(r, "routes"):
            collected.extend(_collect_routes(r))
    return collected


def _gen_api_routes() -> str:
    app = _load_app()
    if app is None:
        return ("| Endpoint | Verb | Purpose |\n"
                "|---|---|---|\n"
                "| _(unable to introspect — run locally with the backend importable)_ | | |")
    rows: List[Tuple[str, str, str]] = []
    for route in _collect_routes(app):
        path = getattr(route, "path", "") or ""
        if not path.startswith("/api"):
            continue
        verb, p, summary = _summarize_route(route)
        if not verb:  # websocket, mount, etc.
            continue
        rows.append((p, verb, summary or ""))
    rows.sort()
    lines = ["| Endpoint | Verb | Purpose |", "|---|---|---|"]
    for p, v, s in rows:
        # Escape pipes in summary
        s_esc = s.replace("|", "\\|")
        lines.append(f"| `{p}` | {v} | {s_esc} |")
    lines.append(f"\n_Total: **{len(rows)}** registered API endpoints._")
    return "\n".join(lines)


def _gen_router_index() -> str:
    routers = sorted((BACKEND_DIR / "routers").glob("*.py"))
    lines = ["| File | Lines |", "|---|---|"]
    total = 0
    for f in routers:
        if f.name == "__init__.py":
            continue
        n = sum(1 for _ in f.open("r", encoding="utf-8"))
        total += n
        lines.append(f"| `routers/{f.name}` | {n} |")
    lines.append(f"| **Total** | **{total}** |")
    return "\n".join(lines)


def _gen_model_index() -> str:
    """List distinct SQLAlchemy models. Prefer the aggregated file."""
    lines = ["| Model | Table |", "|---|---|"]
    try:
        import importlib
        mod = importlib.import_module("models")
        from sqlalchemy.orm import DeclarativeBase

        pairs = []
        for name in dir(mod):
            cls = getattr(mod, name)
            if isinstance(cls, type) and hasattr(cls, "__tablename__"):
                pairs.append((name, cls.__tablename__))
        pairs.sort()
        for name, table in pairs:
            lines.append(f"| `{name}` | `{table}` |")
        lines.append(f"\n_Total: **{len(pairs)}** ORM models._")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"| _(introspection failed: {exc!r})_ | |")
    return "\n".join(lines)


GENERATORS: Dict[str, Callable[[], str]] = {
    "role_matrix": _gen_role_matrix,
    "role_aliases": _gen_role_aliases,
    "api_routes": _gen_api_routes,
    "router_index": _gen_router_index,
    "model_index": _gen_model_index,
}


# ─────────────────────────────────────────────────────────────────────
# Rewriter
# ─────────────────────────────────────────────────────────────────────


def _rewrite(md: str) -> Tuple[str, List[str]]:
    """Return (new_md, list_of_blocks_touched). Blocks whose names
    aren't in GENERATORS are left untouched (so writers can add manual
    AUTO-BLOCK-shaped comments for their own use if needed)."""
    touched: List[str] = []

    def repl(match: re.Match) -> str:
        name = match.group(1)
        gen = GENERATORS.get(name)
        if gen is None:
            return match.group(0)  # unknown block — leave as-is
        body = gen().strip()
        touched.append(name)
        return f"<!-- AUTO:BEGIN {name} -->\n{body}\n<!-- AUTO:END {name} -->"

    new_md = BLOCK_RE.sub(repl, md)
    return new_md, touched


def _sync_file(path: Path, check_only: bool) -> Tuple[bool, List[str]]:
    """Return (changed, blocks_touched)."""
    if not path.exists():
        return False, []
    md = path.read_text(encoding="utf-8")
    new_md, touched = _rewrite(md)
    changed = new_md != md
    if changed and not check_only:
        path.write_text(new_md, encoding="utf-8")
    return changed, touched


def _emit_html() -> Path:
    """Render a single-page HTML view combining every manual for the
    in-app viewer at `frontend/public/docs/IFPI_Master_Manual.html`."""
    try:
        import markdown  # type: ignore
    except ImportError:
        print("[build_docs] `markdown` not installed — skipping HTML render",
              file=sys.stderr)
        return Path()

    combined = []
    for f in MANUAL_FILES:
        if not f.exists():
            continue
        combined.append(f"<!-- === {f.name} === -->\n")
        combined.append(f.read_text(encoding="utf-8"))
        combined.append("\n\n---\n\n")
    body = markdown.markdown("".join(combined),
                             extensions=["tables", "fenced_code", "toc"])
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>IFPI Master Manual</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:960px;"
        "margin:2rem auto;padding:0 1rem;line-height:1.55;color:#0f172a}"
        "table{border-collapse:collapse}th,td{border:1px solid #cbd5e1;"
        "padding:6px 10px}code{background:#f1f5f9;padding:1px 4px;"
        "border-radius:3px}pre{background:#0f172a;color:#f8fafc;"
        "padding:1em;overflow:auto;border-radius:6px}"
        "h1,h2,h3{border-bottom:1px solid #e2e8f0;padding-bottom:.3em}"
        "</style></head><body>"
        + body + "</body></html>"
    )
    out = REPO_ROOT / "frontend" / "public" / "docs" / "IFPI_Master_Manual.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="Exit 1 if regeneration would change any file (CI gate)")
    ap.add_argument("--html", action="store_true",
                    help="Also emit HTML render at frontend/public/docs/IFPI_Master_Manual.html")
    args = ap.parse_args()

    any_change = False
    for path in MANUAL_FILES:
        changed, touched = _sync_file(path, check_only=args.check)
        marker = "DRIFT" if (changed and args.check) else ("REGEN" if changed else "OK")
        blocks_str = ", ".join(touched) if touched else "(no auto-blocks)"
        print(f"[{marker}] {path.name}  →  {blocks_str}")
        if changed:
            any_change = True

    if args.check and any_change:
        print("\n❌ Docs are stale. Run `python backend/scripts/build_docs.py` "
              "and commit the result.", file=sys.stderr)
        return 1

    if args.html:
        out = _emit_html()
        if out and out.exists():
            print(f"[HTML] {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
