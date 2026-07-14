# IFPI ↔ ERP360 Go-Live Checklist

> **Purpose:** the single sheet to run through when we're ready to pull the trigger. Every item here is either (a) blocking go-live, (b) a coordination step with the ERP360 team, or (c) a known compliance gap that should be closed before / soon after cutover.
>
> **Status legend:** ✅ done · ⏳ open / not yet started · 🔧 in progress · 🟨 waiting on external
> **Last updated:** 2026-02-12 (Iter 35)

---

## 🔴 P0 — Go-live blockers (must be green before flipping DNS / announcing)

### Cross-app integration (shipped in preview, needs prod re-run)

- [x] SSO exchange endpoint accepts ERP360 HS256 JWT ✅
- [x] Webhook receiver `/api/erp360/webhooks/user` with HMAC + idempotency ✅
- [x] Scoped role rewrite (§7.3 clobber fix) ✅ Iter 35
- [x] Form-POST binding on `/api/auth/sso-exchange` (§1.1 CORS-immune) ✅ Iter 35
- [x] `GET /api/erp360/sync/status` returns `ready: true` in preview ✅
- [x] Live server-to-server webhook delivery proven (event `3a2e957a-...` → 202) ✅
- [ ] 🟨 **ERP360 to flip tile from fetch → form-POST binding** — IFPI side ready; ERP360 agent said "awaiting IFPI confirmation" (stale note; IFPI confirmed shipped). Ping when flipped.
- [ ] ⏳ Browser click-through smoke test in preview after tile flip → screenshots on both sides
- [ ] ⏳ Browser click-through smoke test on **deployed** URLs (final go-live gate)

### Infrastructure provisioning (IFPI side — from PRD)

- [ ] ⏳ **Neon Postgres** (or Cloudflare Hyperdrive-backed Postgres) provisioned; connection string in deploy secrets as `DATABASE_URL`
- [ ] ⏳ **Cloudflare R2** (or S3) bucket provisioned; keys in deploy secrets (`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL` for R2)
- [ ] ⏳ **Resend** account + API key in deploy secrets (`RESEND_API_KEY`, `SMTP_FROM_EMAIL`); DNS records (SPF, DKIM, DMARC) verified for sending domain
- [ ] ⏳ **Sentry** project created + DSN in deploy secrets (`SENTRY_DSN`)
- [ ] ⏳ **Emergent LLM key** balance topped up + auto-top-up enabled

### Deployment (both apps)

- [ ] ⏳ **Deploy IFPI backend + frontend** (Emergent deployment path per Support guidance)
- [ ] 🟨 **ERP360 deploys their app** (their side)
- [ ] ⏳ Set `CORS_ORIGINS` on IFPI deployment secret = `https://<erp360-deployed-domain>` (comma-separated if multiple)
- [ ] 🟨 ERP360 sets equivalent env on their side pointing at IFPI's deployed origin
- [ ] ⏳ Redeploy both to pick up the origin allowlists
- [ ] ⏳ Verify `GET /api/erp360/sync/status` on **deployed** IFPI returns `ready: true`

### Secret rotation at cutover (do NOT reuse preview secrets in prod)

- [ ] ⏳ **Rotate `ERP360_SSO_SHARED_SECRET`** (a.k.a. `IFPI_SSO_SHARED_SECRET` on ERP360's side) — coordinate same-clock swap
- [ ] ⏳ **Rotate `IFPI_WEBHOOK_OUTBOUND_SECRET`** — same-clock swap
- [ ] ⏳ Swap `IFPI_BASE_URL` (ERP360 side) → IFPI's deployed domain
- [ ] ⏳ Swap `IFPI_WEBHOOK_OUTBOUND_URL` (ERP360 side) → IFPI's deployed `/api/erp360/webhooks/user`
- [ ] ⏳ Confirm `SSO_ENABLED=true` on IFPI deployment
- [ ] ⏳ Confirm `AUTH_COOKIE_SAMESITE=none` and `AUTH_COOKIE_SECURE=true` on IFPI deployment (both mandatory for cross-domain SSO — do NOT revert)

### Content & staff readiness

- [ ] ⏳ **Staff dogfooding** — content team onboarded to AI Authoring Suite; ≥3 real courses built end-to-end (Course → Lessons → Quizzes → Certificate → Analytics visible)
- [ ] ⏳ Admin `admin@ifpi.org` password rotated from `admin123` and stored in the ops password manager (production account, NOT the preview default)
- [ ] ⏳ At least one production Owner + Manager + Instructor account provisioned via ERP360 SSO (end-to-end validation of the JIT flow)

### Go / no-go gate

- [ ] ⏳ On-call runbook printed / bookmarked (`docs/IFPI_SETUP_MANUAL.md` §H — "When things go wrong")
- [ ] ⏳ Rollback plan reviewed — Emergent rollback tested against a checkpoint
- [ ] ⏳ Announcement email drafted for staff (link + login guide)

---

## 🟡 P1 — Should be closed BEFORE cutover if time allows, else within 2 weeks after

### Compliance gaps in the ERP360 contract (from `IFPI_INTEGRATION_HANDOFF.md` §7)

- [x] ✅ **§7.4 Per-org connection state** (Iter 36) — `organizations.integrations` JSONB shipped with `erp360_settings` / `is_erp360_connected` / `erp360_org_slug` / `erp360_sso_enabled` helpers. Webhook receiver + SSO JIT-provisioner now resolve users **only within the org identified by payload/claim `org_slug`** — no more cross-tenant email-collision matching. Fallback to default org preserved for single-tenant preview. **Small remaining item:** admin endpoint `PATCH /api/admin/organizations/{id}/integrations/erp360` to actually configure the mapping in multi-tenant prod. Today it works for single-tenant preview via `slug` auto-match.
- [ ] ⏳ **§7.1 Entitlement abstraction** — must land BEFORE any Stripe integration or that becomes rip-and-replace. Create `Entitlement { org_id, user_id, course_id, source: 'stripe'|'erp360'|'admin_grant', valid_until }`; wire enrollment reads through it; Stripe webhooks (later) write into it; ERP360 lite-billing webhooks (P2.1) write the same shape.
- [x] ✅ **§7.2 Verified-email link tightening** (Iter 36) — `jit_provision` refuses first-time link with 409 Conflict if a matching native account has `email_verified_at IS NULL`. Ops must reconcile before the user can SSO. Blocks the account-takeover vector where an attacker signs up native (unverified) then hopes an ERP360 user later shares that email.
- [x] ✅ **§6.3 Timestamp replay window** (Iter 36) — `X-ERP360-Timestamp` enforced within ±5 min (configurable via `ERP360_TIMESTAMP_SKEW_SECONDS`). Missing header still accepted (dedup mandatory downstream); malformed → 400; out-of-window → 401. Supports both ISO-8601 UTC and unix epoch seconds.

### API surface hardening

- [ ] ⏳ **`/api/v1/` versioning namespace** — add versioned aliases for `/api/auth/sso-exchange`, `/api/erp360/webhooks/user`, `/api/erp360/sync/status`. Keep unversioned aliases for ≥1 sprint. Prevents shape-change breakage for any 3rd party consumer.
- [x] ✅ **SQL-backed idempotency store for `X-ERP360-Event-Id`** (Iter 36) — new `erp360_seen_events` table with PK on `event_id`. Uses INSERT-with-unique-conflict semantics; concurrent workers can't both accept the same event. Regression test proves persistence across backend restart.
- [ ] ⏳ **Shared contract test fixture** — 🟨 waiting on ERP360 to publish their `contract_fixtures.json`; when they do, wire it into `backend/tests/` as a nightly CI check.
- [ ] ⏳ **Admin endpoint to configure ERP360 connection per-org** — `PATCH /api/admin/organizations/{id}/integrations/erp360` with `{connected, org_slug, sso_enabled, billing_mode}`. Backing model (`Organization.integrations` JSONB) shipped in Iter 36; only the admin route + UI remaining.

### Load-readiness (before or shortly after cutover)

- [x] ✅ **Webhook rate limiter** (Iter 37) — 200 req/min per signing-key prefix, sliding window, in-process LRU eviction. Returns `429 Too Many Requests` with `Retry-After: 60` before signature verification. Located: `services/rate_limits.py::erp360_webhook_limiter`. Unit + integration tests locked in.
- [x] ✅ **Postgres advisory lock on `(org_id, user_sub)`** (Iter 37) — applied in the webhook `role_changed`/`user_deactivated` handlers AND `SSOService.jit_provision`. Concurrent events for the SAME user serialize outside the transaction; different users run in parallel. No-op on SQLite (single-writer already serializes). Located: `services/db_locks.py::advisory_lock`.
- [x] ✅ **`@retry_on_deadlock()` decorator** (Iter 37) — wraps `_replace_erp360_roles`; catches Postgres `40P01`/`40001` and retries once with 50-200ms jitter. Non-retriable codes (e.g. `23505` unique violation) propagate immediately. Located: `services/db_locks.py::retry_on_deadlock`.
- [x] ✅ **Background-task audit offload** (Iter 37) — `role_changed` and `user_deactivated` handlers ship the 202 response before writing the audit row. Audit writer opens its own DB session and swallows exceptions (background failures never affect the already-sent response). Located: `routers/erp360_sync.py::_audit_bg`.
- [x] ✅ **Locust scenario scaffold** (Iter 37) — 3 concurrent user classes (WebhookUser, SsoUser, ReadHeavyUser) at `backend/loadtests/locustfile.py` + README with headless + web-UI invocations. Meaningful numbers require the deployed Postgres surface (SQLite in preview dominates measurement).
- [x] ✅ **Observability: per-request query counter + latency log line** (Iter 38 Phase A) — `[req] method=X path=Y status=N duration_ms=T queries=Q cid=...` on every request; real-time `[n+1?]` warning above `N_PLUS_ONE_THRESHOLD` (default 25). Sentry-ready format (drops into `SENTRY_DSN` when set, no code change).
- [x] ✅ **N+1 audit + fixes on 4 hot endpoints** (Iter 38 Phase A) — `/api/admin/users` (1542→7), `/api/gamification/leaderboard` (103→5), `/api/live-sessions` (86→4), `/api/catalog` (52→6). Regression tests lock in the gains at 3× baseline.
- [x] ✅ **Pagination on `/api/admin/users` + `/api/admin/audit-digest`** (Iter 38 Phase A) — audit-digest now uses SQL `COUNT` + 300-row sample (constant memory regardless of audit table size).
- [x] ✅ **Progress decoupling via Postgres outbox** (Iter 38 Phase B) — new `progress_outbox` table + background worker polling `SELECT FOR UPDATE SKIP LOCKED` every 2s. `track_slide_view` enqueues instead of inserting synchronously; SlideView writes happen asynchronously. Idempotent via SlideView's unique constraint. Exponential backoff + MAX_ATTEMPTS on failed rows.
- [x] ✅ **Atomic-transaction audit on multi-step enrollment/assessment** (Iter 38 Phase B) — audit performed, existing code already follows single-commit-boundary pattern for enrollment / complete_course / assessment submission. ERP360 webhook path uses background-task audit (stronger than atomic — never blocks response).
- [x] ✅ **`@retry_on_deadlock` extended to mutation endpoints** (Iter 38 Phase B) — applied to `POST /api/courses/{id}/enroll` and `POST /api/courses/{id}/complete`. Regression tests lock in the `__wrapped__` attribute so a refactor can't silently drop it.
- [x] ✅ **In-process TTL cache with graceful degrade** (Iter 38 Phase C) — `services/cache.py` with `@cached_view` decorator and `@degrade_on_db_error` decorator that serves stale value + `X-Served-Stale: true` header on `OperationalError`. Ready for wiring onto specific hot public reads (deferred to keep this iteration bounded).
- [x] ✅ **Circuit breaker on certificate PDF generation** (Iter 38 Phase C) — 3-state breaker (CLOSED/OPEN/HALF_OPEN) on `download_certificate_pdf`. After 5 consecutive failures, returns 503 + Retry-After: 30 instead of 500. Learning flow stays fully live.
- [ ] ⏳ **Actual 10× load-test run against the deployed environment** — establishes real p95/p99 numbers.
- [ ] ⏳ **Postgres connection pool tuning** — env-driven, no code changes; set defaults after load-test.
- [ ] ⏳ **Sentry DSN + alert rules** — pool exhaustion, `429` spike, any 5xx on SSO or webhook routes. Code is already Sentry-ready; just needs the DSN.
- [ ] ⏳ **Remaining pagination gaps** — `/api/admin/affiliate/*`, `/api/admin/terms`, `/api/subscriptions`, `/api/catalog/organizations`. Safe at current traffic, add limits when we hit scale.

### Payments (only if commercial launch)

- [ ] ⏳ **Stripe integration** (native path, `billing_mode: "native_stripe"`) — currently learners can enroll in paid courses for free; no enforcement logic. Required only if we're charging for courses at launch.
  - Depends on §7.1 entitlement abstraction landing first.
  - Requires user-provided Stripe API keys (test key is available in pod env for dev; prod keys needed at cutover).

---

## 🟢 P2 — Nice-to-have, backlog for after go-live

### Contract & integration

- [ ] ⏳ **§4 Outbound webhook dispatcher (IFPI → ERP360)** — sender for `learner.invited`, `enrollment.completed`, `certificate.issued`, `ai.spend.threshold`, `course.published`. Requires ERP360 to first expose their inbound receiver + provide the shared `X-IFPI-Signature` HMAC secret. Highest-value event is `certificate.issued` (surfaces on ERP360 person profile — this is the "why we did the integration" moment).
- [ ] ⏳ **§P1.1 ERP360 lite-billing subscription webhooks** (billing_mode: `erp360`) — writes into the same `Entitlement` table as native Stripe; ERP360 is merchant-of-record for that mode.
- [ ] ⏳ **HMAC v2 contract** — if we ever need to add nonce, key ID, or timestamp-in-signed-string, that's a v2 (never mutate the v1 spec in place). Not needed for go-live.

### Performance & scale

- [ ] ⏳ **Flip `USE_PGVECTOR=true`** after reaching ~1000 embedding chunks (fallback cosine works for MVP). Migration already prepped; just an env toggle.
- [ ] ⏳ **`server.py` domain-driven decomposition** — file is still ~800 lines; split into `routers/` sub-modules by domain. Any refactor here must preserve middleware order (CORS before auth).

### DX & observability

- [ ] ⏳ **Structured logging + correlation IDs** across all inbound integration flows (partially done — `cid=` prefix in supervisor logs). Add ERP360-side event_id to every log line touching a webhook payload.
- [ ] ⏳ **Sentry alert rules** — alert on any `role_changed` returning 5xx, any SSO failure spike (>5 in 60s), any HMAC verification failure (indicates a secret rotation issue).
- [ ] ⏳ **Runbook drill** — simulate a secret rotation on both sides; confirm no missed webhooks, no login outages, replay handling works.

---

## 📌 Rules to remember at cutover (do not violate)

1. **Cookies:** `AUTH_COOKIE_SAMESITE=none` + `AUTH_COOKIE_SECURE=true` — required for cross-domain SSO. Never flip to `Lax`.
2. **CORS:** `CORS_ORIGINS` is explicit-list only. Never `*` when credentials are enabled (browsers reject; also a security hole).
3. **Secrets:** Never in git. Rotate at cutover, then every 90 days. Same-clock swap on both sides.
4. **URL rotation on either side** = same-day paired env update on the other side.
5. **Contract changes** to the SSO JWT claims or webhook payload = new v2 endpoint. Never mutate v1 in place.
6. **Dedup key** is `user.sub` (ERP360 `person_id`). Never fall back to email for identity matching (email fallback exists ONLY for first-time verified link).
7. **IFPI-native roles** (INSTRUCTOR, cohort assignments) are IFPI's source-of-truth. ERP360 webhooks touch ONLY `source='erp360'` rows.

---

## 📞 Who owns what

| Track | IFPI side (this repo) | ERP360 side (their repo) |
|---|---|---|
| Contract spec | Mirror of `IFPI_INTEGRATION_HANDOFF.md` | Canonical `IFPI_INTEGRATION_HANDOFF.md` |
| SSO exchange endpoint | ✅ implemented | Mints token, submits form |
| Webhook receiver | ✅ implemented | Signs + retries + DLQ |
| Deploy secrets | `CORS_ORIGINS`, `ERP360_SSO_SHARED_SECRET`, `IFPI_WEBHOOK_OUTBOUND_SECRET`, `SSO_ENABLED`, etc. | Their equivalents |
| Rotation coordinator | Ops on IFPI side | Their ops |
| Contract fixtures | Consumes | Publishes |

---

## 🎯 The "flip the switch" order

When ready to go live:

1. Provision infra (Neon / R2 / Resend / Sentry) → deploy IFPI backend+frontend.
2. ERP360 deploys.
3. Rotate both shared secrets on both sides same-clock.
4. Set `CORS_ORIGINS` on IFPI deploy = ERP360's deployed origin; ERP360 does the reverse.
5. Redeploy both.
6. `GET https://<ifpi-prod>/api/erp360/sync/status` → confirm `ready: true`.
7. Server-to-server dry-run: ERP360 fires `test-ping` webhook → IFPI 202s.
8. Browser click-through: staff account SSO from ERP360 tile → lands signed-in on `<ifpi-prod>/dashboard`.
9. Send announcement.
10. Monitor Sentry + admin audit log for the first 48h.

Anything in P1 that isn't done at step 1 is a known-risk item — decide per row whether to accept the risk or delay.
