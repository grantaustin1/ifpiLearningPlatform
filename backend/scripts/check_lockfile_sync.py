"""Guard: package.json and yarn.lock must stay in sync (Iter 45).

Reproduces the failure class behind CI's `yarn install --frozen-lockfile`
("Your lockfile needs to be updated") without touching the network: every
dependency entry `name@range` in frontend/package.json must have a matching
resolution key in frontend/yarn.lock. Added or version-bumped deps whose
lockfile was not regenerated are reported.

Run:  python /app/backend/scripts/check_lockfile_sync.py   (exit 1 on drift)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def main() -> int:
    pkg = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    lock = (FRONTEND / "yarn.lock").read_text(encoding="utf-8")

    deps: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        deps.update(pkg.get(section, {}))

    missing = []
    for name, range_ in sorted(deps.items()):
        if range_.startswith(("file:", "link:", "workspace:")):
            continue  # local refs never appear as registry keys
        if f"{name}@{range_}" not in lock:
            missing.append(f"{name}@{range_}")

    if missing:
        print("❌ yarn.lock is OUT OF SYNC with package.json — CI's")
        print("   `yarn install --frozen-lockfile` will fail. Missing keys:")
        for m in missing:
            print(f"   • {m}")
        print("   Fix: cd /app/frontend && yarn install   (then commit BOTH files)")
        return 1

    print(f"lockfile sync OK — {len(deps)} package.json deps all resolved in yarn.lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
