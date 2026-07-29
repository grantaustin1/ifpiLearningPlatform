"""Pre-finish invariant check.

Runs the fast guards that must be green before an agent calls `finish`:

1. **Docs regen**: `build_docs.py` regenerates every AUTO-BLOCK so
   the on-disk manuals match `app.routes` + `models` + `routers`.
2. **Docs drift check**: `build_docs.py --check` exits 0 → no more
   staleness sneaking through.
3. **Endpoint signature lint** (both passes): no ForwardRef leaks
   at endpoint definition or decorator definition time.
4. **Docs completeness test**: `pytest tests/test_docs_completeness.py`
   confirms every route is documented.

Exit code 0 = safe to `finish`. Exit code 1 = STOP, fix something.

Usage:
    python /app/backend/scripts/pre_finish_check.py

Add to your finish flow — this catches the exact class of bug that
tripped CI when docs drifted between iterations (Iter 39 postmortem).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], label: str) -> bool:
    print(f"\n── {label} ──")
    r = subprocess.run(cmd, cwd=str(_BACKEND),
                       capture_output=True, text=True, timeout=180)
    tail = (r.stdout + r.stderr).strip().splitlines()[-5:]
    for line in tail:
        print(f"  {line}")
    ok = r.returncode == 0
    print(f"  → {'✅ pass' if ok else f'❌ fail (exit {r.returncode})'}")
    return ok


def main() -> int:
    checks = [
        (["python", "scripts/build_docs.py"],
         "1. Regenerate docs (mutates on-disk manuals)"),
        (["python", "scripts/build_docs.py", "--check"],
         "2. Verify no drift (regen was idempotent)"),
        (["python", "scripts/lint_endpoint_signatures.py",
          "--check-decorators"],
         "3. Endpoint signature + decorator lint"),
        (["python", "-m", "pytest", "tests/test_docs_completeness.py",
          "-q", "--tb=short"],
         "4. Docs completeness test suite"),
    ]

    all_ok = True
    for cmd, label in checks:
        if not _run(cmd, label):
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✅  Pre-finish check PASSED. Safe to call the finish tool.")
        return 0
    print("❌  Pre-finish check FAILED. Fix the above BEFORE calling finish.")
    print("    Typical fix: docs drifted → this script's step (1) has")
    print("    already regenerated them; just commit and re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
