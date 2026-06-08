#!/bin/bash
# IFPI Secret Scanner — ported from ERP360 (scripts/security/scan-secrets.sh).
# Detects hardcoded API keys, JWTs, AWS keys, etc. before commit / in CI.
# Usage: ./scripts/security/scan-secrets.sh [--ci]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CI_MODE=false
[[ "$1" == "--ci" ]] && CI_MODE=true

ISSUES_FOUND=0
WARNINGS=0

echo "=== IFPI Secret Scanner ==="
echo "Date: $(date)"
echo ""

# Patterns
declare -A PATTERNS=(
    ["API_KEY_LITERAL"]='api_key\s*=\s*["\x27][A-Za-z0-9_-]{20,}["\x27]'
    ["BEARER_HARDCODED"]='Bearer\s+[A-Za-z0-9_-]{20,}'
    ["PASSWORD_LITERAL"]='password\s*=\s*["\x27][^"\x27]{8,}["\x27]'
    ["SECRET_KEY_LITERAL"]='secret[_-]?key\s*=\s*["\x27][A-Za-z0-9_-]{16,}["\x27]'
    ["JWT_TOKEN"]='eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'
    ["PRIVATE_KEY"]='-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'
    ["AWS_ACCESS_KEY"]='AKIA[0-9A-Z]{16}'
    ["SENDGRID_KEY"]='SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}'
    ["TWILIO_SID"]='AC[a-f0-9]{32}'
    ["STRIPE_LIVE"]='sk_live_[A-Za-z0-9]{24,}'
)

# Where to scan (and where NOT to)
SCAN_DIRS=("backend" "frontend/src" "scripts" "docs")
IGNORE='(/node_modules/|/__pycache__/|/\.venv/|/\.git/|/uploads/|\.env\.example|test_credentials\.md|\.lock$|package-lock\.json|yarn\.lock|migrations?/|/alembic/versions/)'

for dir in "${SCAN_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  for name in "${!PATTERNS[@]}"; do
    HITS=$(grep -rEnI "${PATTERNS[$name]}" "$dir" 2>/dev/null \
      | grep -vE "$IGNORE" \
      | grep -vE '#\s*nosec|#\s*pragma:\s*allowlist' || true)
    if [ -n "$HITS" ]; then
      echo -e "${RED}[FAIL]${NC} $name detected:"
      echo "$HITS" | sed 's/^/    /'
      ISSUES_FOUND=$((ISSUES_FOUND + $(echo "$HITS" | wc -l)))
    fi
  done
done

echo ""
if [ $ISSUES_FOUND -gt 0 ]; then
  echo -e "${RED}FAIL — $ISSUES_FOUND potential secrets found.${NC}"
  echo "Annotate intentional matches with '# nosec' or '# pragma: allowlist'."
  $CI_MODE && exit 1 || exit 1
fi
echo -e "${GREEN}OK — no hardcoded secrets detected.${NC}"
exit 0
