# IFPI Deploy Runbook

**Purpose:** Zero-guessing production deployment when ERP360 dev is ready.
**Last updated:** 2026-02-13 (post Iter 39)
**Target:** Emergent Deploy platform (or any Kubernetes / container host with FastAPI + PostgreSQL support)

---

## Pre-flight checklist (do these FIRST)

- [ ] ERP360 team confirms the SSO tile has flipped from `fetch` → form-POST binding
- [ ] Neon Postgres project created, **pooled** connection string in hand
- [ ] Cloudflare R2 bucket created (`ifpi-media-prod`), API token issued
- [ ] Resend account created, sending domain verified (SPF + DKIM + DMARC green)
- [ ] Sentry project created (Platform: FastAPI), DSN in hand
- [ ] Stripe LIVE-mode API key issued from https://dashboard.stripe.com (or keep `sk_test_emergent` for staged rollout)
- [ ] Coordinate the shared `ERP360_SSO_SHARED_SECRET` value with the ERP360 team (rotate ANY value they used in preview — never reuse dev secrets in prod)

---

## Step 1 · Copy env template & fill in real values

```bash
# On your workstation (do NOT commit this file):
cp /app/backend/.env.production.example ~/ifpi-secrets.env
# Edit ~/ifpi-secrets.env — paste real values for the 4 categories.
```

**Generate any random secrets that require it:**

```bash
# JWT secret (48 bytes url-safe)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# SMTP encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# ERP360 shared secret (64 bytes)
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Step 2 · Push secrets to deploy platform

**Option A — Emergent Deploy UI:**
1. Open the app → **Deploy** → **Environment Variables**
2. Paste each `KEY=value` from `~/ifpi-secrets.env` (one per line supported)
3. Click **Save** — a redeploy is triggered automatically

**Option B — CLI (if platform supports):**
```bash
while IFS='=' read -r key val; do
  [[ $key = \#* || -z $key ]] && continue
  emergent deploy env set "$key=$val"
done < ~/ifpi-secrets.env
```

---

## Step 3 · Deploy precheck + Alembic migrations against Neon

**Run the built-in precheck** (validates env, runs `alembic upgrade head`, pre-warms the pool):

```bash
DATABASE_URL='<paste neon pooled url>' \
ENVIRONMENT=production \
python /app/backend/scripts/deploy_precheck.py --strict
```

Exit codes: `0` = safe to serve, `1` = blocker (fix and re-run), `2` = internal error.

**What the precheck validates** (verified 2026-02-13 with the current `.env.production.example`):
- `JWT_SECRET`, `SMTP_ENCRYPTION_KEY` not dev-defaults
- `AUTH_COOKIE_MODE=on`, `AUTH_COOKIE_SECURE=true`
- `ALLOWED_ORIGINS` set + no wildcards
- `STORAGE_BACKEND=s3` + `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` populated
- `SYSTEM_SMTP_*` chain complete (or explicit warning if omitted)
- `PUBLIC_BASE_URL` set
- `EMERGENT_LLM_KEY`, `SEED_ADMIN_PASSWORD` set
- `ALLOW_TEST_TOKEN_HEADER=false`
- Alembic `upgrade head` runs cleanly
- DB pool pre-warm succeeds (proves Neon connectivity + creds)

**Seed the default org + admin + learner** (idempotent — safe to re-run):

```bash
DATABASE_URL='<paste neon pooled url>' \
python -m seed.seed_minimal
```

Records the admin credentials in `/app/memory/test_credentials.md` — swap to a real production password immediately:

```bash
curl -X POST https://ifpi.example.com/api/auth/change-password \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"admin123","new_password":"<real-prod-pw>"}'
```

---

## Step 4 · Configure Stripe webhook endpoint

1. Stripe dashboard → **Developers** → **Webhooks** → **Add endpoint**
2. Endpoint URL: `https://ifpi.example.com/api/webhook/stripe`
3. Events to listen for: `checkout.session.completed`, `payment_intent.succeeded`
4. Copy the **Signing secret** → set as `STRIPE_WEBHOOK_SECRET` in the deploy env
5. Trigger a test event from the Stripe dashboard — check Sentry / logs for `stripe.handle_webhook` success

---

## Step 5 · Post-deploy smoke tests

Save this as `smoke.sh` and run against the LIVE URL:

```bash
#!/usr/bin/env bash
set -euo pipefail
URL="${1:-https://ifpi.example.com}"

echo "── 1. Root health ──"
curl -sf "$URL/api" | jq

echo "── 2. Public probe ──"
curl -sfD - "$URL/api/erp360/sync/status" | grep -iE "HTTP|x-cache|x-api-version"

echo "── 3. v1 alias ──"
curl -sfD - "$URL/api/v1/erp360/sync/status" | grep -iE "HTTP|x-api-version"

echo "── 4. Login + auth/me ──"
TOKEN=$(curl -sf "$URL/api/auth/login" \
  -H "Content-Type: application/json" -H "X-Return-Token: true" \
  -d '{"email":"admin@ifpi.org","password":"<real-prod-pw>"}' \
  | jq -r '.access_token // .token')
[[ -z "$TOKEN" ]] && { echo "LOGIN FAILED"; exit 1; }
curl -sf "$URL/api/auth/me" -H "Authorization: Bearer $TOKEN" | jq '.email, .roles'

echo "── 5. Catalog cache ──"
curl -sfD - "$URL/api/public/catalog" -H "Authorization: Bearer $TOKEN" | grep -i x-cache
curl -sfD - "$URL/api/public/catalog" -H "Authorization: Bearer $TOKEN" | grep -i x-cache   # 2nd call = HIT

echo "── 6. Sentry probe (should trigger an event you can see) ──"
# GET a route that intentionally 500s — safe to run once.
# Add a `/api/_sentry-test` endpoint to your app before enabling this.

echo "── 7. R2 upload smoke ──"
echo "smoke-test" > /tmp/r2-smoke.txt
curl -sf -X POST "$URL/api/authoring/media/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/r2-smoke.txt" | jq '.url'
# Verify the returned URL 200s

echo "── 8. Resend email smoke ──"
curl -sf -X POST "$URL/api/admin/email/test-send" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"you@example.com","subject":"smoke","body":"deploy verified"}'
# Check inbox + Resend dashboard for "Delivered"

echo "✅ ALL SMOKE TESTS PASSED"
```

---

## Step 6 · 10× load test with locust

**Prereq:** `smoke.sh` must be green — never load-test a broken deploy.

```bash
cd /app/backend
export ERP360_SSO_SHARED_SECRET="<same as deploy env>"
export IFPI_WEBHOOK_OUTBOUND_SECRET="<same as deploy env>"

locust -f loadtests/locustfile.py \
  --host https://ifpi.example.com \
  --users 500 --spawn-rate 25 \
  --run-time 5m \
  --headless \
  --html /tmp/locust-report-$(date +%Y%m%d-%H%M).html
```

**Success criteria** (from `/app/backend/loadtests/locustfile.py` header):
- p95 response time < 5s on every endpoint
- Zero 500s in DB-write paths
- Failure rate < 1% across all users

If a threshold breaks:
- Deadlock 500s → check `@retry_on_deadlock` is applied to the failing endpoint (Iter 38 Phase B)
- Slow tail → look for missing `@cached_view` on the endpoint (Iter 38 Phase C)
- 429s from rate limiter → tune `services/rate_limits.py` bucket sizes

---

## Step 7 · Cutover — flip ERP360's IFPI_BASE_URL

Coordinate with ERP360 team:
1. They update their env: `IFPI_BASE_URL=https://ifpi.example.com`
2. They re-issue their SSO shared secret if needed (must match `ERP360_SSO_SHARED_SECRET` on our side)
3. Trigger the "Continue with ERP360" tile from their portal
4. Verify a fresh user JIT-provisions in IFPI, gets redirected to their dashboard, and can access any entitled course

---

## Rollback plan

If step 5 or 6 catches a critical bug:

1. **Immediate mitigation:** In Emergent Deploy → **History** → click the last known-good deploy → **Redeploy**
2. **Data safety:** Neon has point-in-time restore in the console (Storage → Restore) — restore to a timestamp before the bad deploy
3. **Feature flags:** Toggle off any broken feature via `PUT /api/admin/feature-flags/<key> {"enabled": false}` (Iter 38 hot-read caching invalidates instantly)

---

## Post-cutover checklist

- [ ] `SSO_ENABLED=false` in prod env (per-org `integrations.erp360.sso_enabled` is authoritative — §7.4)
- [ ] For each real customer org: `PATCH /api/admin/organizations/{id}/integrations/erp360 {"connected": true, "sso_enabled": true, "org_slug": "<erp360 slug>", "billing_mode": "erp360"}`
- [ ] Sentry alert rules configured (p95 latency, 5xx rate, DB pool exhaustion)
- [ ] Feature flag `marketplace` intentionally off if you're not selling B2B seat licences yet
- [ ] Announce SSO cutover to end users (comms email via Resend)

---

## Files this runbook depends on

| File | Purpose |
|---|---|
| `/app/backend/.env.production.example` | Env template — copy, fill, push |
| `/app/backend/loadtests/locustfile.py` | 10× load test scenarios |
| `/app/backend/seed/seed_minimal.py` | Idempotent default org + admin + learner seed |
| `/app/backend/scripts/deploy_precheck.py` | Env validator + Alembic runner + pool pre-warm |
| `/app/memory/GO_LIVE_CHECKLIST.md` | Compliance / hardening state |
| `/app/memory/test_credentials.md` | Test-only credentials (delete after cutover) |

---

## Emergency contacts

| System | Where to look |
|---|---|
| DB down | Neon console → Ops → Metrics + Support ticket |
| Stripe webhook failures | Stripe dashboard → Developers → Webhooks → **Recent Deliveries** |
| Email deliverability | Resend dashboard → **Emails** tab → click any failure |
| Runtime errors | Sentry → **Issues** → filter by `environment:production` |
