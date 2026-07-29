"""Pre-finish invariant check (parallelized).

Runs the fast guards that must be green before an agent calls `finish`.

Sequence:
  Step 1 (sequential) — regenerate docs (mutates on-disk manuals).
  Steps 2-4 (parallel) — the three independent verifications:
     • docs-drift check (must be idempotent after step 1)
     • endpoint signature + decorator lint
     • docs completeness pytest suite

Exit 0 = safe to `finish`. Exit 1 = STOP, fix something.

Usage:
    python /app/backend/scripts/pre_finish_check.py

See `/app/memory/AGENT_WORKFLOW.md` for the rationale.
"""
from __future__ import annotations

import concurrent.futures as _cf
import subprocess
import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], label: str) -> tuple[str, bool, str]:
    """Run one subprocess. Returns (label, ok, tail-output)."""
    r = subprocess.run(cmd, cwd=str(_BACKEND),
                       capture_output=True, text=True, timeout=180)
    tail = "\n".join(
        ("  " + line) for line in
        (r.stdout + r.stderr).strip().splitlines()[-5:]
    )
    return label, r.returncode == 0, tail


def _emit(label: str, ok: bool, tail: str) -> None:
    print(f"\n── {label} ──")
    print(tail)
    print(f"  → {'✅ pass' if ok else '❌ fail'}")


def main() -> int:
    started = time.perf_counter()

    # Step 1 — MUST be sequential: it mutates the docs the other
    # steps then verify.
    label1, ok1, tail1 = _run(
        ["python", "scripts/build_docs.py"],
        "1. Regenerate docs (mutates on-disk manuals)",
    )
    _emit(label1, ok1, tail1)
    if not ok1:
        print("\n❌ Regen failed — later steps skipped.")
        return 1

    # Steps 2-4 — independent, run concurrently.
    parallel = [
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
    with _cf.ThreadPoolExecutor(max_workers=len(parallel)) as pool:
        futures = [pool.submit(_run, cmd, lbl) for cmd, lbl in parallel]
        # Preserve input order for consistent output regardless of
        # which subprocess finished first.
        results = [f.result() for f in futures]

    for label, ok, tail in results:
        _emit(label, ok, tail)
        if not ok:
            all_ok = False

    elapsed = time.perf_counter() - started
    print("\n" + "=" * 60)
    print(f"Elapsed: {elapsed:.1f}s")
    if all_ok:
        print("✅  Pre-finish check PASSED. Safe to call the finish tool.")
        return 0
    print("❌  Pre-finish check FAILED. Fix the above BEFORE calling finish.")
    print("    Typical fix: docs drifted → step (1) already regenerated")
    print("    them; just commit and re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
