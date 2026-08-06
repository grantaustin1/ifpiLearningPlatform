#!/usr/bin/env bash
# Iter 30 — Frontend safety net.
#
# Runs `yarn typecheck` (tsc --noEmit) so a missing-import bug like the
# iter-29 ImportsPage.tsx incident (which would black-screen the app
# via CRA's compile-problems overlay) cannot ship.
#
# Wire into CI:
#   - name: Frontend type-check
#     run: bash scripts/ci_typecheck.sh
#
# Wire into pre-commit hook (optional):
#   `git config core.hooksPath .githooks` and drop this in
#   .githooks/pre-commit — see README for details.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
echo "==> Running yarn typecheck (tsc --noEmit)..."
yarn typecheck
echo "==> Type-check passed ✓"
