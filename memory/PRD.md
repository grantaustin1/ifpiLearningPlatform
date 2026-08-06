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

## 2026-08-06 — Pulled branch 20260731 into Emergent preview
- Checked out `origin/20260731`. Branch tip commit 76521b06 had UNRESOLVED merge-conflict markers committed in 114 files (bad merge of the emergent-init scaffold with real history); restored all file contents from clean parent 6d926451.
- Recreated missing .env files (backend: SQLite DATABASE_URL, JWT_SECRET; frontend: REACT_APP_BACKEND_URL).
- Preview fixes (dev-env only): pinned webpack-dev-server resolution 5.x→4.x (CRA5 dev server incompatible with v5); removed brace-expansion@^5 resolution (crashed minimatch 3 / fork-ts-checker with "expand is not a function").
- Code fix: AttendanceModal.tsx used `useConfirm()` return as callable — destructured `{ confirm, ConfirmDialog }` and rendered `<ConfirmDialog />` (was a TS2349 compile error).
- Purged 93 test-debris courses (Stripe Test / Entitlement Test / Paid E2E / Ent Inspect) from ifpi_lms.db via test_debris_cleanup with extended patterns.
- Verified: backend /api/health OK, admin login OK (forced change-password gate as designed), frontend compiles clean, backend smoke suite tests/test_ifpi_api.py 25 passed / 2 skipped.
