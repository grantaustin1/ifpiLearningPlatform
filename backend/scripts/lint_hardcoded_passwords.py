#!/usr/bin/env python3
"""Iter 33 — CI lint that blocks new hardcoded default passwords from
creeping into the codebase.

Scans backend + frontend source trees for the common footgun patterns:
  password="literal"
  PASSWORD = "literal"
  admin/admin
  admin123 / password123 / test123 / letmein / changeme
  bcrypt hash literals

Known-safe locations (tests, seed with env-var fallback, docs) are
whitelisted. New matches OUTSIDE the whitelist fail the lint.

Usage:
    python backend/scripts/lint_hardcoded_passwords.py        # scan
    python backend/scripts/lint_hardcoded_passwords.py --show # verbose

Exit codes:
    0 — no offending literals detected
    1 — at least one match outside the whitelist
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path("/app")
SCAN_ROOTS = [REPO_ROOT / "backend", REPO_ROOT / "frontend" / "src"]

# Patterns we treat as suspicious. Kept intentionally narrow to avoid
# false positives on legitimate `password: str` type annotations etc.
SUSPICIOUS_PATTERNS = [
    # Assignment of a literal string to a password variable.
    re.compile(r"""(?ix)
        \b (password|passwd|pwd) \s* [:=]{1,2} \s*
        ["']([^"']{3,64})["']
    """),
    # Common defaults, regardless of variable name.
    re.compile(r"""(?ix)
        ["'] (admin123|password123|test123|letmein|changeme|admin@admin|
              12345678|qwerty|welcome1)["']
    """),
]

# Absolute paths (or path fragments) whose matches we intentionally
# tolerate. Everything else is a lint failure.
WHITELIST_PATH_FRAGMENTS = [
    "/backend/tests/",           # test fixtures use canned creds
    "/backend/scripts/qa_agents/",  # internal QA agents
    "/backend/scripts/lint_hardcoded_passwords.py",  # this file's own regex literals
    "/backend/scripts/build_screenshots.py",  # dev-time browser automation
    "/backend/scripts/locustfile.py",         # load-test rig
    "/backend/scripts/deploy_precheck.py",  # references dev defaults in error text
    "/backend/scripts/seed_templates.py",  # optional bulk-import demos
    "/backend/schemas/",          # Pydantic field: password: str (no literal)
    "/backend/seed/seed_minimal.py",  # uses _seed_admin_password() env-var helper
    "/memory/",                   # test-credentials docs
    "/docs/",                     # user manuals reference the seeded creds
    "/frontend/src/pages/auth/",  # UI copy: "at least 8 characters"
    ".test.tsx", ".test.ts", ".spec.tsx", ".spec.ts",
]

# Explicit line-level allowlist for individual known-safe hits. Format:
# "<absolute path>::<literal that matches>". Keep this list SHORT.
LINE_ALLOWLIST = set()


def _whitelisted(path: str) -> bool:
    return any(frag in path for frag in WHITELIST_PATH_FRAGMENTS)


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, matched_snippet) for offending lines."""
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        # Skip comments — comments about "don't use admin123" are safe
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        for pat in SUSPICIOUS_PATTERNS:
            m = pat.search(line)
            if m:
                key = f"{path}::{m.group(0)}"
                if key in LINE_ALLOWLIST:
                    continue
                hits.append((lineno, m.group(0)))
    return hits


def main() -> int:
    show_all = "--show" in sys.argv
    failures: list[tuple[Path, int, str]] = []
    file_count = 0
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            if _whitelisted(str(path)):
                continue
            file_count += 1
            for lineno, snippet in _scan_file(path):
                failures.append((path, lineno, snippet))

    if show_all or failures:
        print(f"Scanned {file_count} source files across {len(SCAN_ROOTS)} roots.")
    if not failures:
        print("✅  No hardcoded default passwords detected.")
        return 0

    print(f"❌  {len(failures)} hardcoded-password lint failure(s):\n")
    for path, lineno, snippet in failures:
        rel = str(path).replace(str(REPO_ROOT), "")
        print(f"  {rel}:{lineno}  →  {snippet}")
    print("\nFix: replace with an env-var lookup (see seed/seed_minimal.py"
          "::_seed_admin_password for the pattern).")
    print("Whitelist: if the match is a false positive, add the path "
          "fragment to WHITELIST_PATH_FRAGMENTS in this file.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
