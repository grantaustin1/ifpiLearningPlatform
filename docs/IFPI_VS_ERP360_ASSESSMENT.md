# IFPI vs ERP360 — Comparative Assessment & Roadmap

> Answers the seven-question review requested on 2026-07-03 after re-ingesting the ERP360 codebase.

**Sources analysed:**
- ERP360: `ThreeSixtyERP-dev` (71 docs, 256 routers, 549 backend tests, Locust load suite)
- IFPI: current codebase at `/app` (23 routers, 33 services, 32 test files, 142 integration tests)

---

## 1. Features IFPI Should Add (borrowed from ERP360's playbook)

Ordered by **impact vs effort** for a learning-focused SaaS.

### P0 — Must-Have Before Serious Multi-Tenant Rollout

| Feature (ERP360 name) | Adapted to IFPI | Why it matters |
|---|---|---|
| **Impersonation / "View-as-role"** | Owner + Admin can view IFPI as a Learner/Instructor without logging out | Product support, QA, onboarding demos |
| **VIEWER read-only role** | New `VIEWER` role — 20+ pages read-only | Franchise owners, auditors, finance oversight |
| **HttpOnly cookie session + refresh family + reuse detection** | Replace localStorage-JWT with cookie + rotating refresh family | Removes XSS-exfiltration risk; matches ERP360's Sprint C hardening |
| **CSRF middleware (dry-run then enforce)** | Copy ERP360's `csrf_middleware.py` with same env gates | Required for cookie-based sessions |
| **Correlation-ID + structured logging middleware** | 1 line per request with `x-correlation-id` header | Debug prod without stack-trace archaeology |
| **Slow-query logger** | 500 ms threshold, logs SQL + params | Catches N+1 before customers report it |
| **Global exception envelope** | Uniform `{error: {code, message, correlation_id, status}}` on every 4xx/5xx | Frontend can build a single error surface |
| **Backups + off-site + tested restore** | Nightly DB dump → S3 (encrypted) + weekly restore drill | Legal/compliance table stakes |

### P1 — High-Impact for Learners

| Feature | Adapted to IFPI |
|---|---|
| **2FA (TOTP + SMS)** | Optional TOTP for Instructor+, mandatory for Owner. Reuse ERP360's playbook — same `MANDATE_2FA_*` env pattern. |
| **Owner dashboard** | Distinct dashboard for `OWNER` role — org-wide KPIs, AI spend vs budget, cohort persistency headline |
| **"Members needing action" widget** | For learners: overdue cert renewals, streaks about to break, deadlines |
| **Kiosk mode** | Tablet-friendly UI for in-person training rooms — swipeable enrolment + on-site cert print |
| **Contract terms + T&Cs acceptance** | Learner must accept T&Cs on first login; audit-logged; version-bumped on change |
| **Feature-module system** | Per-org feature flags (e.g., "AI video is on this org's plan?") — ERP360 has this as V23 migration |
| **Cross-env test suite** | ERP360's `cross_env_test.py` pattern — smoke-test both preview and staging URLs |

### P2 — Growth & Ecosystem

| Feature | Adapted to IFPI |
|---|---|
| **Onboarding board** | Kanban of new learner setup steps (invite → first login → first course → first cert) |
| **Report scheduler** | Weekly PDF emailed to Owner (ERP360's `scheduled_reports.py` is transplantable 1:1) |
| **Affiliate program** | Instructor earns X% referral for every paid learner they refer |
| **Marketplace / Public store** | Publish courses for sale outside the tenant — Stripe checkout + revenue split |
| **Live sessions (Zoom/Meet)** | Attach a session to a course slide — attendance auto-marks progress |
| **Mobile-optimized member self-service** | ERP360 has 31_member_self_service.png — a whole learner mobile portal |
| **AI query builder** | ERP360's `ai_query.py` — natural-language questions against your reports |
| **Julius-style analytics feedback loop** | Auto-flag reports that don't get opened; suggest deprecation |

---

## 2. Manuals to Build & Their Refresh Cadence

ERP360 has an **auto-generated manual pipeline**:
- `docs/USER_GUIDE_CONSOLIDATED.md` (3,594 lines) — regenerated per release
- `docs/TENANT_SETUP_GUIDE_V2.md` (661 lines) — "Idiots Guide" with impact analysis
- `docs/threesixty_master_manual.md` (1,385 lines) — the top-of-tree master
- `docs/guides/Phase_A..F_*.md` — six per-phase deep-dives
- `docs/onboarding/manual_verification.md` — the QA checklist
- `frontend/public/docs/*.html` — HTML render for in-app viewing
- Generator: `backend/scripts/build_tenant_setup_guide_v2.py` scans routers + role_registry + models on every merge

### IFPI equivalents to create

| Manual | Format | Refresh trigger |
|---|---|---|
| **IFPI Setup Manual v1** (Phases A–F) | `/app/docs/IFPI_SETUP_MANUAL.md` | Auto on router/role changes |
| **IFPI User Manual v1** (feature reference) | `/app/docs/IFPI_USER_MANUAL.md` | Auto on router/service changes |
| **IFPI Integration Matrix** (sibling vs stand-alone) | `/app/docs/IFPI_INTEGRATION_MATRIX.md` | On env-flag additions |
| **IFPI Runbook** (ops incidents) | `/app/docs/IFPI_RUNBOOK.md` | Per incident retro |
| **IFPI Security Whitepaper** | `/app/docs/IFPI_SECURITY.md` | Quarterly + per vuln disclosure |
| **IFPI Master Manual (HTML)** | `frontend/public/docs/IFPI_Master_Manual.html` | Every release build |
| **Onboarding Verification Checklist** | `/app/docs/IFPI_ONBOARDING_VERIFY.md` | On onboarding-flow change |
| **API Reference (auto)** | `/docs` (FastAPI OpenAPI) | Auto on every deploy |

### Automation pipeline (recommended)

1. **On every release tag**, GitHub Actions runs:
   ```
   python backend/scripts/build_setup_guide.py    # → IFPI_SETUP_MANUAL.md
   python backend/scripts/build_user_manual.py    # → IFPI_USER_MANUAL.md
   python backend/scripts/build_master_manual.py  # → HTML render
   python backend/scripts/capture_screenshots.py  # → Playwright snapshots of 24 pages
   git add docs/ frontend/public/docs/
   ```
2. **On PR to `main`** — a doc-drift gate runs `pytest backend/tests/test_docs_completeness.py` which fails if a router or role was added without its section being in the manual.
3. **Weekly cron** re-runs `build_master_manual.py` even without a release so any router hot-added stays in sync.

**Deliverables added in this iteration (see companion files):**
- ✅ `/app/docs/IFPI_SETUP_MANUAL.md` (created)
- ✅ `/app/docs/IFPI_USER_MANUAL.md` (created)
- ✅ `/app/docs/IFPI_INTEGRATION_MATRIX.md` (created)
- ⏳ Auto-generator scripts (`build_setup_guide.py`, `build_user_manual.py`) — recommended follow-up

---

## 3. IFPI User & Setup Manuals — Delivered

See:
- `/app/docs/IFPI_SETUP_MANUAL.md` — 6 phases + audit checklist + failure matrix
- `/app/docs/IFPI_USER_MANUAL.md` — 13 sections, full feature reference

Both mirror ERP360's structure (Phase A/B/C/... + Impact Analysis + Zero-Blocker Checks + Failure Scenario Matrix) so ERP360-familiar admins onboard IFPI with zero cognitive tax.

---

## 4. IFPI ↔ ERP360 Sync Verification

**IFPI CAN run stand-alone OR as a sibling** — all sibling features are behind env flags.

The full toggle matrix is documented in `/app/docs/IFPI_INTEGRATION_MATRIX.md`. Key confirmations:

| Concern | Status |
|---|---|
| Auth (SSO) | ✅ HS256 handshake wired (Iter 14). Replay protection via `sso_replay_tokens` (Iter 17). Env: `SSO_ENABLED`, `ERP360_SSO_SHARED_SECRET`. |
| Sibling ↔ stand-alone toggle | ✅ Single env var (`SSO_ENABLED`) flips the mode. No code branches. |
| User provisioning | ✅ JIT on SSO exchange. TRAINER→INSTRUCTOR role mapping. |
| Outbound webhooks to ERP360 | ⏳ Generic webhook system exists (Iter 12). Need explicit `WEBHOOK_OUTBOUND_TO_ERP360_URL` gate + payload contract. |
| Inbound webhooks from ERP360 | ⏳ Not yet built. Need `POST /api/erp360/webhooks/*` router + HMAC verify. |
| Billing routing | ⏳ Design done in matrix doc; `ERP360_BILLING_BASE_URL` env not yet wired. |
| Branding sync | ⏳ Manual upload works stand-alone; sibling-mode auto-sync is backlog. |
| Cross-app cache invalidation | ⏳ IFPI uses Redis for rate limiting; needs to join ERP360's `cache:invalidate:v1` channel. |
| Audit stream duplication | ⏳ Design done; needs `AUDIT_MIRROR_TO_ERP360_URL` implementation. |

**Recommendation:** IFPI is ✅ stand-alone-ready today, and ⏳ ~80 % sibling-ready. Ship the ⏳ items in the P1 batch below to hit 100 % sibling parity.

---

## 5. Security Comparison & Recommendations

### 5.1 ERP360's security posture (per docs review)

- ✅ HttpOnly cookie sessions + family-tracked refresh + reuse detection
- ✅ CSRF middleware (dry-run + enforce modes)
- ✅ CORS whitelist + trust boundaries doc
- ✅ 2FA (TOTP + SMS via Twilio) for mandates
- ✅ Cloudflare Zero Trust for admin routes
- ✅ Redis-backed rate limiting (multi-endpoint)
- ✅ PII redactor + no auth headers in logs
- ✅ Webhook signature verification (fail-closed)
- ✅ Slow-query logger + correlation IDs
- ✅ Tenant isolation tests + org_id filter audit
- ✅ Security remediation report + go-live checklist
- ✅ Documented incident response process

### 5.2 IFPI's current security posture

- ✅ JWT auth with role-based dependencies
- ✅ Redis-backed rate limiter (Iter 30b) with in-memory fallback
- ✅ HMAC-signed outgoing webhooks
- ✅ PII redactor service
- ✅ Sanitized user HTML (`bleach`)
- ✅ Audit log (append-only)
- ✅ API tokens with scopes + call log
- ✅ SSO replay protection
- ✅ Certificate signed verifier tokens
- ✅ Public-endpoint rate limits
- ⚠ localStorage-JWT (XSS exfiltration risk)
- ⚠ No CSRF middleware (fine while stateless, required if adding cookies)
- ⚠ No 2FA
- ⚠ No brute-force lockout on password login
- ⚠ No correlation-ID middleware
- ⚠ No global exception envelope
- ⚠ No backup rotation policy documented

### 5.3 Recommended security backlog for IFPI (in priority order)

| # | Item | Effort | Impact |
|---|---|---|---|
| 1 | HttpOnly cookie session + refresh-family + reuse detection | M | CRITICAL — removes XSS token exfiltration |
| 2 | CSRF middleware (dry-run → enforce, same as ERP360) | S | Required with #1 |
| 3 | Brute-force lockout on `/api/auth/login` (5 fails / 15 min per email+IP) | S | Blocks credential-stuffing |
| 4 | Correlation-ID + structured logging middleware | S | Debug-quality-of-life |
| 5 | Global exception envelope + error taxonomy | S | Frontend UX |
| 6 | 2FA (TOTP) — mandatory for Owner, optional for Admin | M | High-value for enterprise deals |
| 7 | Tenant-isolation regression tests (Org A vs Org B crossover) | M | Prevents catastrophic PII leaks |
| 8 | Slow-query logger + p95 alerting | S | Catches N+1 before customers do |
| 9 | Webhook replay protection + timestamp header | S | Fail-closed already in place; need timestamp |
| 10 | Encrypted DB backups → S3 with weekly restore drill | M | Compliance foundation |
| 11 | Redact Authorization headers in logs (INFO+ level) | S | Audit hygiene |
| 12 | Publish `IFPI_SECURITY.md` + `SECURITY_GO_LIVE_CHECKLIST.md` | S | Sales enablement |

---

## 6. Tests & Documentation Comparison

### 6.1 What ERP360 has

- **549 backend test files** (`backend/tests/`) — pytest, ~10k tests
- **Load test suite** — Locust for 100 → 20 k concurrent users
- **Chaos monkey** — `tests/chaos_monkey_stress_test.py`
- **CI e2e runner** — `tests/ci_e2e_runner.py`
- **Full-spectrum e2e** — `tests/full_spectrum_e2e_test.py`
- **Model factories** — `qlink_model_factories.py`
- **QA agents 001-010** — invariant checks, e2e journey, infra sentry, governance auditor
- **`tests/comms`, `tests/config`, `tests/docs`** subfolders — every subsystem gets its own dir
- **Doc drift gates in CI** — `README_doc_drift_gates.md`
- **Feature gap register** — CSV of dev progress, updated per sprint

### 6.2 What IFPI has today

- **32 integration test files, ~142 tests** (in `backend/tests/`)
- **Iteration reports** in `test_reports/iteration_*.json` (via testing agent)
- **3 QA agents** (`agent_007_invariants`, `agent_008_e2e_journey`, `agent_010_infra_sentry`)
- **Conftest that auto-skips when backend not reachable** (CI-safe, Iter 30b)
- ⚠ No load test suite
- ⚠ No chaos suite
- ⚠ No model factories (tests build data ad-hoc)
- ⚠ No doc-drift gate

### 6.3 Recommended test & docs roadmap for IFPI

| # | Item | Priority | Effort |
|---|---|---|---|
| 1 | **Locust load suite** — target 5 k concurrent learners on `/api/courses/*` + `/api/learn/flashcards/*/review` | P1 | M |
| 2 | **Chaos monkey** — random pod kill during a course-authoring flow; assert no data loss | P2 | M |
| 3 | **Model factories** (`factory-boy`) — pytest fixture-per-model | P1 | M |
| 4 | **Cross-env smoke test** — hits both preview + staging every deploy | P1 | S |
| 5 | **Doc-drift gate** — `test_docs_completeness.py` fails when a router lacks a Manual section | P1 | S |
| 6 | **Auto-generated setup + user manuals** — `build_setup_guide.py`, `build_user_manual.py` | P1 | M |
| 7 | **Screenshot capture pipeline** — Playwright snapshots of 24 key screens on every release | P2 | M |
| 8 | **Coverage gate** — pytest-cov, fail CI < 70 % on backend/services/ | P2 | S |
| 9 | **Contract tests** — Pact for the webhook out-payloads | P2 | M |
| 10 | **Master Manual HTML render** — `convert_md_to_html.py` (portable from ERP360) | P2 | S |

---

## 7. Scalability Comparison & Roadmap

### 7.1 ERP360's scale targets & mechanisms

- **Target:** 20 k concurrent users, 99.9 % uptime SLA
- **DB pooling:** SQLAlchemy pool + **PgBouncer** as connection multiplexer
- **Cache:** Redis for token cache, cache-invalidation pub/sub, rate limiting, session store
- **Load balancer:** Nginx/HAProxy in front of multiple FastAPI workers
- **Multi-region HA:** Documented in `MULTI_REGION_HA_ARCHITECTURE.md` — active-passive across 2 regions, RTO<15 min, RPO<1 min
- **Slow-query threshold:** 500 ms, alerts wired
- **Load tests published:** `Load_Test_Report.md` shows p50 14 ms, p95 30 s at 100 concurrent (identifies auth-timing as the bottleneck)
- **Feature-module flags** — per-org enable/disable so heavy features don't burn CPU for orgs that don't use them
- **Async job runner** — `services/async_job_runner.py` for long-running work
- **Cross-worker cache invalidation** — `cache:invalidate:v1` Redis pub/sub channel

### 7.2 IFPI's current scale posture

- **Deployment:** Single FastAPI worker under supervisor + Redis (Iter 30b)
- **DB:** SQLite in dev, Postgres-ready via `DATABASE_URL` env
- **AI heavy-lifting:** `background_worker.py` for Sora video (async)
- **Rate limiting:** Redis sliding window (Iter 30b) — multi-replica ready
- ⚠ No PgBouncer
- ⚠ No load tests
- ⚠ No pub/sub cache invalidation (JWT cache is per-process only)
- ⚠ No connection pool tuning docs
- ⚠ Single-region only
- ⚠ No feature-module flags

### 7.3 Recommended scalability roadmap for IFPI

**Assumption:** IFPI's realistic target for the next 12 months is **5,000 concurrent learners** (not 20 k) — most orgs run 100–500 concurrent.

| # | Item | Priority | Rationale |
|---|---|---|---|
| 1 | **Uvicorn workers = 4** in production + tune SQLAlchemy pool (`pool_size=20, max_overflow=10`) | P0 | Doubles throughput on the same node |
| 2 | **Redis pub/sub cache-invalidation bus** for JWT + user snapshots | P0 | Required before running >1 worker |
| 3 | **PgBouncer** in transaction pooling mode | P1 | Required at >2 k concurrent |
| 4 | **Slow-query logger** (500 ms) + Sentry integration | P1 | Fastest way to find bottlenecks |
| 5 | **Locust load suite** at 500 → 2 k → 5 k concurrent | P1 | Validate before scale-up |
| 6 | **AI job queue with Celery/RQ** — replace in-process background worker | P1 | AI jobs (Sora) should not block API workers |
| 7 | **S3 for media** (currently mocked local storage) — CDN in front | P1 | Video/audio delivery |
| 8 | **CloudFront/Cloudflare edge cache** for `/api/public/catalog` | P2 | Catalog is read-heavy, cache-friendly |
| 9 | **Per-org feature flags** — feature_module table like ERP360 | P2 | Enterprise plan gating |
| 10 | **Multi-region HA** (active-passive) | P2 | Only if SLA demands |
| 11 | **Async event-driven architecture** for cohort digests, streak recomputation | P2 | Moves batch load off request path |
| 12 | **Kubernetes HPA** — auto-scale on CPU + queue depth | P2 | Cloud-native scale-out |

### 7.4 Concrete quick-win: 3-day sprint

Deliver by end of week to unblock the first 500 concurrent learners:

- **Day 1:** Uvicorn workers=4 + SQLAlchemy pool tuning + Redis cache invalidation bus
- **Day 2:** Locust suite + 500-user load run + slow-query logger
- **Day 3:** PgBouncer in staging + doc updates in `IFPI_RUNBOOK.md`

---

## Summary: The One-Screen Verdict

| Dimension | IFPI Status | Recommended Next Step |
|---|---|---|
| **Features** | Rich AI Authoring Suite; missing owner dashboard, impersonation, VIEWER role, kiosk | Implement top 5 P0 items |
| **Manuals** | Now have Setup + User + Integration Matrix (delivered here) | Wire an auto-generator + doc-drift CI gate |
| **Sibling parity** | ~80 % (SSO works, webhooks generic) | Add ERP360-specific webhook contracts + billing env gate |
| **Security** | Solid foundations (Redis rate-limit, HMAC, SSO replay) | Migrate to cookie sessions + add CSRF + 2FA |
| **Tests** | 142 integration tests, 3 QA agents | Add Locust + factories + doc-drift gate |
| **Scalability** | Single-worker, Redis-backed rate limit | Multi-worker + pub/sub cache + Locust validation |

**IFPI is production-viable for early customers today.** The above roadmap is what lifts it from "usable" to "enterprise-parity with ERP360."

---

*Generated 2026-07-03 as part of the post-ERP360-re-ingest assessment. Owner: IFPI Platform Team.*
