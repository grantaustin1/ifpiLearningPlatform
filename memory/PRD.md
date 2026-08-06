# IFPI Learning Platform — PRD

Multi-tenant LMS built on the ERP360 tech stack (FastAPI + SQLAlchemy + React 19).

- **Iteration history** → `/app/memory/CHANGELOG.md`
- **Backlog (prioritized)** → `/app/memory/ROADMAP.md`
- **Test credentials** → `/app/memory/test_credentials.md`

## Original problem statement
Assess the ERP360 and IFPI Next.js codebase and build the IFPI learning app as a sibling application. Rebuild IFPI using the ERP360 tech stack. Support:

- Multi-tenant Organizations with JWT-based Auth
- AI Course + Quiz Builder (Emergent LLM Key)
- S3 configuration (currently MOCKED)
- SCORM / xAPI support
- Slide Versioning + Bulk Imports
- Outgoing HMAC Webhooks
- SSO + API Tokens
- Comprehensive AI Authoring Suite

## User personas
- **Super Admin (SaaS)** — cross-org configuration, marketplace curation.
- **Organization Admin / Instructor** — creates courses, assigns to cohorts,
  moderates live sessions, marks attendance, views funnel + drop-off analytics.
- **Learner** — enrolls, plays slides, RSVPs to live sessions, earns badges +
  certificates, keeps a learning streak.
- **API-token principal** — external integrations calling the read-only
  catalog API with scoped credentials.

## Core requirements (invariants)
1. **Multi-tenant** — every row scoped by `organization_id`. Cross-tenant
   endpoints (marketplace, public catalog, public certificate verify) are
   explicit and read-only.
2. **HttpOnly Cookie auth** in production (JWT bearer for tests only, gated
   by `ALLOW_TEST_TOKEN_HEADER=true`).
3. **Rate limiting** on public endpoints (login, verify, marketplace).
   Client IP resolved via `X-Forwarded-For` (K8s ingress) with test-only
   `X-Test-Client-Ip` override.
4. **Idempotent writes** wherever a background retry might replay
   (attendance certificates, notifications, outbox webhooks).
5. **All ObjectId/PK values serialized as JSON-safe strings**; datetimes
   in ISO-8601 UTC.
6. **PDF branding** — certificates inherit org's logo, primary colour,
   signature block, and footer text.
7. **Documentation drift protection** — every new endpoint must appear in
   `IFPI_USER_MANUAL.md` after running `python backend/scripts/build_docs.py`.

## Health snapshot (2026-02, post iter-39)
- Backend routes: 260+ endpoints (auto-indexed in the manual). Every endpoint reachable under BOTH `/api/*` and `/api/v1/*` (Iter 39 versioned alias middleware).
- Frontend: React 19, 65+ pages/components.
- Background workers: outbox drain, webhook retry, cohort celebrations,
  weekly digest, live-session reminders, nightly test-debris cleanup,
  streak-break nudge (Iter 27), scheduled reports, streak leaderboard
  digest (Iter 30), compliance auto-report (Iter 31, env-gated),
  progress-outbox drain @ 2s (Iter 38 Phase B).
- Scalability guards (Iter 38 A/B/C): per-request query-count middleware,
  N+1 fixes on 4 hot endpoints, retry-on-deadlock on mutations,
  in-process TTL cache (`X-Cache: HIT|MISS`) + graceful-degrade on
  `/api/erp360/sync/status`, `/api/feature-flags`, `/api/public/catalog`,
  circuit breaker on certificate PDF generation.
- Integration hardening (Iter 39): per-org SSO enablement retires global
  `SSO_ENABLED`; ERP360 claim-side `email_verified` required for
  native-account auto-linking; `EntitlementService` decouples enrollment
  from payment-provider specifics; Stripe test-mode wired end-to-end;
  outbound webhook dispatcher IFPI → ERP360 operational in dry-run
  (auto-provisions on org PATCH; flip URL to go live).
- Storage: SQLite (dev + preview) at absolute path
  `sqlite:////app/backend/ifpi_lms.db`. Postgres migration deferred to P2.
- Tests: 585+ pytest tests + 50+ Playwright E2E flows via
  `testing_agent_v3_fork`.

## Related docs
- `IFPI_USER_MANUAL.md` — auto-generated API + model index
- `IFPI_SETUP_MANUAL.md` — role matrix + deployment setup
- `IFPI_INTEGRATION_MATRIX.md` — third-party integration status
- `IFPI_WEBHOOK_EVENTS.md` — outgoing webhook payload reference (Iter 31)
- `IFPI_VS_ERP360_ASSESSMENT.md` — original assessment
- `docs/P2_BACKLOG_SPECS.md` — deep-dive specs for deferred items

## 2026-08-06 (session 2) — Correct merge resolution + full regression green
- DISCOVERY: branch 20260731's broken merge had two divergent parents. The GitHub/Copilot CI line (6d926451, previously restored) had silently DROPPED iterations 42-48 (CourseRating model, covers/featured, reviews, reply/share, landing analytics) during a router-decomposition refactor, and wrongly reverted the Iter-40 fitness rebrand. The Emergent dev line (b7ce3738, 2026-08-01) is the complete app.
- RESOLUTION: working tree switched to b7ce3738 (dev line) as base; removed 70 stale decomposition-package files (routers/misc/, routers/courses/, etc.) that shadowed the monolithic routers; kept backend/conftest.py + pytest.ini for local pytest runs.
- Env restored per repo changelog: CSRF_ENABLED=true, AUTH_COOKIE_MODE=dual, ALLOW_TEST_TOKEN_HEADER=true, SMTP_ENCRYPTION_KEY, SSO_ENABLED=true, ERP360_SSO_SHARED_SECRET, IFPI_WEBHOOK_OUTBOUND_SECRET, STRIPE_API_KEY, EMERGENT_LLM_KEY.
- Stale-test fixes (code was newer than tests on the dev snapshot): iter6/8 theme slugs (conservatoire→crimson_gold per fitness rebrand), iter30e docs manifest (+erp360-bolt-on, line_count>40), iter23 cleanup dict (+marketplace_optouts), iter23 tavily error envelope, iter26 track-view/dropoff (async outbox semantics), iter36 SSO tokens (+email_verified claim per iter39 tightening), ifpi_api sso_disabled (SSO now enabled), iter24 tampered-token (base64 spare-bit no-op), iter29 rate-limit (pinned bucket+session), iter13 digest tests (isolate from factory orgs), iter4 outbox pagination (page 999999). Added module-scoped debris-purge fixtures to iter41/42/43 catalog tests.
- FULL REGRESSION: 843 passed / 6 skipped / 0 failed (was 101 failed + 48 errors at session start).
- Frontend: tsc clean, full marketplace UI (hero, featured row, native course cover art) verified in browser; admin login + forced password-change gate working.
- NOTE: .env files are gitignored — required env keys are documented above and in memory/DEPLOY_RUNBOOK.md.
