#!/bin/bash
# guard_no_raw_urls.sh — Pre-commit hook: block raw localhost/preview URLs
# Run manually: bash scripts/guard_no_raw_urls.sh [file1 file2 ...]

set -euo pipefail

ERR=0
for f in "$@"; do
    # Skip non-source files, tests, and config templates
    case "$f" in
        *.test.*|*.spec.*|*conftest*|*.env*|*.env.example|*.md|*.yml|*.yaml)
            continue
            ;;
    esac

    # Check for forbidden patterns
    HITS=$(grep -nE 'http://localhost:[0-9]+|\.preview\.emergentagent\.com' "$f" 2>/dev/null || true)
    if [ -n "$HITS" ]; then
        echo "ERROR: Raw URL detected in $f"
        echo "$HITS"
        echo "  → Use env vars (BACKEND_URL, FRONTEND_URL) or config modules instead."
        echo "  → See AGENTS.md §2: Configuration over Literals"
        ERR=1
    fi
done

if [ "$ERR" -ne 0 ]; then
    echo ""
    echo "Fix: Replace raw URLs with centralized config variables."
    exit 1
fi

echo "Raw URL guard: OK"
