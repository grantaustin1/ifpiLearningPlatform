# IFPI Load Tests

Load-test scenarios for the cross-app integration surface. Uses locust
(already installed with pytest).

## Quick start

```bash
cd /app/backend

# Web UI mode — interactive charts at http://localhost:8089
locust -f loadtests/locustfile.py --host http://localhost:8001

# Headless — run 100 users at 10 spawns/sec for 60s, print summary
locust -f loadtests/locustfile.py --host http://localhost:8001 \
    --headless -u 100 -r 10 -t 60s
```

## What it tests

Three concurrent user classes hitting the surface the Iter 37 hardening
was designed to protect:

| User class      | Endpoint                             | Weight |
|-----------------|--------------------------------------|--------|
| WebhookUser     | POST /api/erp360/webhooks/user       | 3      |
| SsoUser         | POST /api/auth/sso-exchange (JSON)   | 2      |
| ReadHeavyUser   | GET  /api/erp360/sync/status         | 1      |

## What to look for

1. **p95 response time > 5s on any endpoint** — API Gateway 504 risk.
2. **Any 500s in the webhook/SSO paths** — deadlock or lock timeout;
   check backend logs for `pgcode=40P01` or `40001`.
3. **`429 Too Many Requests` on webhook** — expected under sustained
   >200 req/min from a single signing key; not a failure, that's the
   rate limiter doing its job.

## What was protected against

- **Rate limiter** (200 req/min per signing key) fails fast on bad-actor
  stampedes without burning HMAC verification CPU.
- **Postgres advisory lock** on `(org_id, user_sub)` in the webhook
  handler AND `SSOService.jit_provision`: concurrent events for the
  SAME user serialize outside the transaction; different users still
  run in parallel.
- **`@retry_on_deadlock()`** on `_replace_erp360_roles`: transient
  40P01/40001 retried once with 50–200ms jitter.
- **Background-task audit writes**: the 202 response ships immediately;
  audit rows land on a background worker (with its own DB session).

## Establishing baseline numbers

Run once against a KNOWN-BROKEN version (say, before Iter 37) and once
after. The delta is your hardening ROI.

At time of writing (2026-02-12), Iter 37 preview baseline against
SQLite: **can't be established in preview** — SQLite's single-writer
model dominates any measurement. Real numbers require the deployed
Postgres surface. Add to go-live checklist step 7 (server-to-server
dry-run).
