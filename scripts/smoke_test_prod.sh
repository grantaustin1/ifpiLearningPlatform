#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# IFPI Learning — Post-deploy smoke test
#
# Usage:
#   ./scripts/smoke_test_prod.sh https://api.learn.ifpi.org
#
# Runs the minimum viable set of checks against a fresh deploy.
# Exits non-zero on any failure. Safe to run in CI.
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backend-base-url>"
    echo "Example: $0 https://api.learn.ifpi.org"
    exit 2
fi

BASE="${1%/}"
FAIL=0

check() {
    local name="$1"; local status="$2"; local expected="$3"
    if [ "$status" = "$expected" ]; then
        echo "  ✅  $name  → $status"
    else
        echo "  ❌  $name  → got $status, expected $expected"
        FAIL=$((FAIL + 1))
    fi
}

echo "─────────────────────────────────────────────────────────"
echo "IFPI Deploy Smoke Test"
echo "  Base URL: $BASE"
echo "─────────────────────────────────────────────────────────"

# 1. Health
S=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health")
check "GET /api/health" "$S" "200"

# 2. Public marketplace (no auth, tests DB reachable)
S=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/marketplace/courses")
check "GET /api/marketplace/courses" "$S" "200"

# 3. Login with seeded admin (tests auth + cookies)
LOGIN_RESP=$(mktemp)
S=$(curl -s -o "$LOGIN_RESP" -w "%{http_code}" -c /tmp/cookies.txt \
    -X POST "$BASE/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"email":"admin@ifpi.org","password":"admin123"}')
check "POST /api/auth/login (seeded admin)" "$S" "200"

# 4. Cookies actually set? Should have ifpi_access + ifpi_refresh
if grep -q "ifpi_access\|access_token" /tmp/cookies.txt 2>/dev/null; then
    echo "  ✅  Login set HttpOnly auth cookies"
else
    echo "  ⚠️  Login did NOT set an auth cookie — check AUTH_COOKIE_MODE=on"
    FAIL=$((FAIL + 1))
fi

# 5. Authenticated /me (tests cookie-based auth end-to-end)
S=$(curl -s -o /dev/null -w "%{http_code}" -b /tmp/cookies.txt \
    "$BASE/api/auth/me")
check "GET /api/auth/me (with cookies)" "$S" "200"

# 6. Docs endpoint (tests OpenAPI schema is served in prod)
S=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/openapi.json")
check "GET /api/openapi.json" "$S" "200"

# 7. CORS preflight from a browser-like Origin
S=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE/api/auth/me" \
    -H 'Origin: '"$BASE" -H 'Access-Control-Request-Method: GET')
check "OPTIONS /api/auth/me (CORS preflight)" "$S" "200"

rm -f "$LOGIN_RESP" /tmp/cookies.txt

echo "─────────────────────────────────────────────────────────"
if [ "$FAIL" -eq 0 ]; then
    echo "✅  All smoke tests passed. Deploy looks healthy."
    echo ""
    echo "Next: change admin@ifpi.org password IMMEDIATELY via the UI."
    exit 0
else
    echo "❌  $FAIL smoke test(s) failed. Investigate before opening to users."
    echo ""
    echo "Common fixes:"
    echo "  • 500 on /api/marketplace/courses  →  DATABASE_URL wrong / migrations didn't run"
    echo "  • 401 on /api/auth/me              →  cookies not being set — check AUTH_COOKIE_SECURE"
    echo "  • CORS 400/405                     →  ALLOWED_ORIGINS doesn't include the origin"
    exit 1
fi
