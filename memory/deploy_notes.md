# Pre-Deploy Safety Pass (2026-06, staff-testing deploy prep)

## What was flipped
- `backend/.env`: `ALLOW_TEST_TOKEN_HEADER=false` (was true) + added `AUTH_COOKIE_SECURE=true`.
- Code guard `settings.test_bypass_enabled` (core/config.py) — requires the env var
  AND non-production ENVIRONMENT. Used at all 5 bypass sites:
  routers/auth.py (x2), core/middleware.py, routers/marketplace_analytics.py,
  routers/public_catalog.py.

## Effects
- `/api/auth/_test/reset-rate-limit` now 404s everywhere.
- `X-Test-Client-Ip` header ignored everywhere.
- `X-Return-Token` header inert (but AUTH_COOKIE_MODE=dual still returns
  access_token in login BODY, so testing agent + legacy pytest suite keep working).
- ~6 legacy pytest files use X-Test-Client-Ip / reset-rate-limit for rate-limit
  bucket isolation (test_iteration26/32/41/42/43, test_public_guides). They may
  flake with 429s when run in bulk. To run them: temporarily set
  `ALLOW_TEST_TOKEN_HEADER=true` in backend/.env, restart backend, run, flip back.

## Post-deploy step (PENDING — user action)
1. User clicks Deploy, gets live URL (https://<app>.emergent.host).
2. User pastes live URL in chat → update `PUBLIC_BASE_URL` in backend/.env
   (currently points at the preview URL; affects OG share images, sitemap,
   email verification links) → user clicks Update Deployment.
3. Frontend share links use window.location.origin — auto-correct on live, no change needed.

## Staff test credentials (UAT tenant)
See /app/memory/test_credentials.md — uat-admin@ifpi.org / uat-learner@ifpi.org.

## Real production (later, before real learners)
- AUTH_COOKIE_MODE=on, Postgres DATABASE_URL, STORAGE_BACKEND=s3, real SMTP,
  rotated JWT_SECRET + seeded passwords. See backend/scripts/deploy_precheck.py.
