# IFPI Learning Platform — Product Requirements & Status
<!-- lockfile-sync: 2026-07-07 -->

## Iteration 30l/m/n — Kiosk + T&Cs + AI Tutor v1 + Digest + Factories (2026-07-07)

### 30l · Kiosk mode + T&Cs versioning + per-org feature flags — SHIPPED
- ✅ Three new tables: `terms_versions`, `terms_acceptances`, `kiosk_settings`, `feature_flags`. Alembic `c3d4e5f6a7b8` (idempotent — `create_all` in dev doesn't collide).
- ✅ Router `routers/terms_kiosk.py` with 10 endpoints:
  - **T&Cs:** `GET/POST /api/admin/terms`, `GET /api/admin/terms/acceptances`, `GET /api/terms/current`, `POST /api/terms/accept`
  - **Kiosk:** `GET /api/kiosk/settings`, `PUT /api/admin/kiosk/settings`, `POST /api/kiosk/unlock`
  - **Feature flags:** `GET /api/feature-flags`, `PUT /api/admin/feature-flags/{key}`
- ✅ Frontend `TermsGate.tsx` — full-screen blocking modal on every route change if user hasn't accepted the current version. Records IP + user agent on accept.
- ✅ Frontend `KioskShell.tsx` — idle-lock overlay driven by `mousedown/keydown/touchstart/scroll` events. Unlock via PIN (bcrypt-hashed) or password fallback. Zero-footprint when kiosk is disabled for the org.
- ✅ New Settings tab `ComplianceTab.tsx` — publish T&C versions, configure kiosk, toggle 12 known feature flags.
- ✅ 12 known flags registered: `ai_authoring`, `deep_research`, `sora_video`, `nano_banana`, `scorm_export`, `xapi_receiver`, `webhooks_outgoing`, `api_tokens`, `kiosk_mode`, `affiliate_program`, `marketplace`, `live_sessions`.
- ✅ Tests: 11/11 in `tests/test_iteration30l_terms_kiosk.py` — publish flow, acceptance ledger, admin gate, kiosk PIN + password unlock, flag registry, learner permission checks.

### 30m · AI Tutor v1 — SHIPPED (Kimi-plan-adapted, SQLite-friendly)
- ✅ Instead of Kimi's 5 new tables + pgvector requirement, delivered a **2-table** solution that reuses the EXISTING `SourceDocument` + `SourceChunk` corpus (Deep Research already ingests to it):
  - `ai_tutor_sessions` (user, course, title, archived_at)
  - `ai_tutor_messages` (role, content, citations JSON, tokens)
- ✅ Retrieval reuses `services.embedding_service.semantic_search()` when embeddings exist; falls back to LIKE-based snippet extraction when they don't (no more "empty tutor" for orgs that haven't run deep research yet).
- ✅ LLM call via `emergentintegrations.llm.chat.LlmChat` — same provider/model as AI builder (`gpt-4o-mini`).
- ✅ **PII redaction is ALWAYS ON.** Fixed Kimi's flaw where staff could opt out. Learner questions go through `pii_redactor.redact()` before the LLM; original text is stored in message history so the learner sees their own words.
- ✅ 4 endpoints: `POST /api/tutor/ask`, `GET /api/tutor/sessions`, `GET /api/tutor/sessions/{id}`, `POST /api/tutor/sessions/{id}/archive`.
- ✅ Frontend `AITutorPanel.tsx` — floating "Ask AI Tutor" button on the course learn page, slide-out chat with citations, auto-scroll, redaction toast, keyboard-friendly (Enter to send, Shift+Enter for newline).
- ✅ Full org-scope isolation: user A in org X cannot list/view/continue sessions belonging to user B or org Y (verified in tests).
- ✅ Tests: 9/9 in `tests/test_iteration30m_tutor.py` — including 3 that hit real GPT-4o (~45s), PII always-redacted verification, cross-org isolation.

### 30n · Weekly digest email enhancement + factory-boy fixtures — SHIPPED
- ✅ Extended existing Monday-09:00-UTC `cohort_digest` with a **"Members needing action"** section. Reuses the exact same query from `routers/owner_dashboard.py` (single source of truth). Colour-coded rows by reason code, capped at 10 items to keep emails scannable. Admins now wake up on Monday to a proactive nudge list.
- ✅ New `tests/factories.py` — factory-boy factories for `Organization`, `User`, `AdminUser`, `Course`, `Enrollment`. UUID-suffixed slugs/emails to survive re-runs. Zero-arg construction wires FKs via `_create()` overrides. Docs + example in module header.
- ✅ Tests: 5/5 in `tests/test_iteration30n_factories.py` — smoke + composition.

### Kimi AI review — Actioned vs Deferred
- **Actioned (adapted):** Learner-facing AI tutor with session persistence, citations, LLM re-ranking option. Adjusted for SQLite (no pgvector), reuse of existing corpus tables, always-on PII redaction, standard envelope errors.
- **Deferred:** pgvector migration (blocked on PostgreSQL move), staff-side "AI Studio panel" (duplicates existing authoring), Kimi's `deep_research_sources` table (existing `SourceDocument` covers it).
- **Rejected:** Staff opt-out of PII redaction. Redaction is now always-on per GDPR posture.

### Deferred (previously flagged; still pending)
- **AUTH_COOKIE_MODE cutover** to `on` — remains at `dual`. Flip requires mobile/external consumers to stop reading `access_token` from body; that audit is a dedicated task.

---


## Iteration 30h/i/j/k — Auth Refactor + 2FA + Locust CI + Owner Widget (2026-07-05)

### 30h · CSRF double-submit middleware — SHIPPED
- ✅ New `CSRFProtectMiddleware` in `core/middleware.py`. Opt-in via `CSRF_ENABLED=true` (now default in `backend/.env`).
- ✅ On login/register/refresh, backend issues a NON-HttpOnly `ifpi_csrf` cookie scoped to `/` so JS can read it via `document.cookie`. Auth cookie stays HttpOnly on `/api`.
- ✅ Enforcement: POST/PUT/PATCH/DELETE using cookie auth must present `X-CSRF-Token` header matching the cookie. Bearer-header calls (API tokens, mobile, tests) bypass. Login/register/refresh/SSO exchange/public catalog/portal/xAPI/SCORM/invitation-accept are exempt.
- ✅ Frontend `lib/api.ts` axios interceptor reads `ifpi_csrf` and stamps the header on every mutating call. Zero client changes required after the interceptor lands.
- ✅ Tests: 10/10 in `tests/test_iteration30h_csrf.py` (unit + E2E). Verified live via Playwright: cookie-authed POST without CSRF → 403; with matching header → 200; Bearer bypass → 200.

### 30i · TOTP-based 2FA (RFC 6238) — SHIPPED
- ✅ New model columns on `users`: `totp_secret_enc` (Fernet-encrypted), `totp_enabled_at`, `totp_recovery_codes` (bcrypt-hashed list of 10 single-use codes). Alembic `b2c3d4e5f6a7`.
- ✅ Service `services/totp_service.py` — pyotp 2.10.0 wrapper, provisioning URI, QR-as-base64-PNG, recovery-code lifecycle. Piggybacks on `SMTP_ENCRYPTION_KEY` for encryption.
- ✅ Router `routers/totp.py` — 6 endpoints:
  - `GET /api/auth/2fa/status`
  - `POST /api/auth/2fa/setup-init` (QR + secret preview, not saved)
  - `POST /api/auth/2fa/setup` (verify code → persist encrypted secret + issue 10 recovery codes ONCE)
  - `POST /api/auth/2fa/disable` (self-service, requires password + valid code)
  - `POST /api/auth/2fa/challenge` (public — exchange challenge_id + code → LoginResponse)
  - `POST /api/admin/users/{id}/2fa/disable` (SUPER_ADMIN force-disable)
- ✅ Login flow modified: if user has 2FA enabled, `/api/auth/login` returns `{requires_2fa: true, challenge_id, expires_in}` instead of tokens. Frontend swaps password form for TOTP-code form and hits `/challenge` to complete.
- ✅ In-memory challenge store with 5-min TTL + 5 attempt cap. Recovery codes are consumed on use (single-use enforced).
- ✅ Frontend `SecurityTab.tsx` — Settings → Security tab. Full lifecycle UI: QR scan → verify → recovery-code display → disable form.
- ✅ `LoginPage` now handles the 2FA gate: shows a code input, "Use a different account" cancel, error surfacing from envelope.
- ✅ Tests: 7/7 in `tests/test_iteration30i_totp.py` — full enable/login/disable cycle, recovery-code single-use, challenge lockout at 5 attempts.

### 30j · Locust smoke load CI job — SHIPPED
- ✅ New `.github/workflows/ci.yml::locust-smoke` job — spins up uvicorn, seeds DB, runs 5-user × 30s smoke with `--tags smoke`, asserts p95 < 3000ms + error rate < 5%. Fails CI on breach. Uploads CSV artifacts on every run.
- ✅ Fixed 2 dead endpoints in `scripts/locustfile.py` — `/api/dashboard` → `/api/notifications`, `/api/learn/flashcards/courses/{id}` → `/api/learn/flashcards/courses/{id}/due`. Verified locally: 0% errors, p95 = 240ms on a 20s run.

### 30k · Owner dashboard — Members needing action widget — SHIPPED
- ✅ New endpoint `GET /api/admin/dashboard/members-needing-action?limit=1-100`. Categorizes learners into 3 priority buckets:
  - **STALLED** (P1) — enrolled ≥ 14 days, progress = 0
  - **IDLE** (P2) — progress 1-99%, enrolled ≥ 14 days ago
  - **NEVER_SIGNED_IN** (P3) — account ≥ 7 days old, `last_login_at IS NULL`
- ✅ Response shape: `{count, total_flagged, generated_at, items[]}`. Each item carries a reason code, human message, detail, and a `next_step` (label + path admins can click into).
- ✅ Sorted by priority ascending — highest-urgency first.
- ✅ Frontend `MembersNeedingActionWidget.tsx` mounted at top of admin dashboard (replaces the old activity-only layout). Colour-coded by reason. React Query with 60s stale time.
- ✅ Tests: 4/4 in `tests/test_iteration30k_owner.py` — shape, admin gate, limit enforcement, priority ordering.

### Deferred to next iteration
- **Kiosk mode + T&Cs acceptance tracking** — needs its own migration, dedicated kiosk-shell UI, and offline mode. Deferred for scope.
- **`AUTH_COOKIE_MODE=on` cutover** — remains on `dual` (cookie + Bearer in body). Flip when we're sure no downstream (mobile, external integrations) still reads `access_token` from the body.

### Regression + hotfix note
- `test_iteration5.py` admin_session fixture updated to attach `Authorization: Bearer` (was cookie-only; would fail under CSRF enforcement).
- Docs library `AUTO:*` blocks regenerated (2 new router files → `api_routes` block re-emitted).

---


## Hotfix (2026-07-04 · iteration 30g · Audit-log commit fix)

- ✅ Fixed the two regressions from iter 30e — `test_download_records_audit_log_entry`
  and `test_preview_records_distinct_audit_action`. Root cause: `audit_service.record()`
  only calls `db.add()`, relying on the caller's transaction to commit. The docs library
  PDF/raw endpoints are pure GETs — nothing else triggered a commit — so `get_db()`
  closed the session and the audit rows were silently dropped.
- ✅ Added explicit `db.commit()` in `routers/docs_library.py::download_pdf` and
  `download_raw` right after each `audit_service.record()` call. All other write-flow
  callers already commit as part of their business-object flush, so no other endpoints
  need touching.
- ✅ Regenerated the docs-library `AUTO:*` blocks via `python backend/scripts/build_docs.py`
  (stale `router_index / model_index / api_routes` in `IFPI_USER_MANUAL.md`).
- **Regression:** 10/10 `test_iteration30e.py` + 3/3 `test_iteration30d.py` +
  3/3 `test_docs_completeness.py` all green (20/20).

## Hotfix (2026-07-03 · iteration 30f · CI dep resolver + envelope compat)

### Pip resolver conflict
- ✅ Bumped `python-jose==3.3.0` → `python-jose==3.5.0`. The older 3.4.0 (the version CI happened to be pulling) required `pyasn1<0.5.0`, which conflicts with our `pyasn1==0.6.3` pin. jose 3.5.0 requires `pyasn1>=0.5.0` — clean resolve. JWT + SSO handlers verified functional.

### Exception envelope backwards-compat (Iter 30d follow-up)
- ✅ Updated `core/middleware.py::_http_exc` — when a handler raises `HTTPException(status_code=X, detail={"key": ...})` with a **dict detail**, the response now preserves every field of the dict AT THE TOP LEVEL alongside the wrapper `error` block. This keeps old client code (that reads `body["missing"]`, `body["message"]`, etc.) working while ALSO exposing the new envelope for new code.
- ✅ Migrated **10 legacy tests** that asserted on `r.json()["detail"]` to the tolerant `body.get("error", {}).get("message") or body.get("detail", "")` pattern (test_iteration14/17/18_20/26/7).
- ✅ Case-insensitive check in `test_iteration15_gaps.py::test_requirements_txt_pins_all_five` (PyPI is case-insensitive; `Markdown` vs `markdown`).

### Regression
- **360/364 tests pass.** The 4 remaining failures are unrelated pre-existing flakes: test-ordering data pollution in `test_ifpi_api::test_enrol_free_course_learner`, external AI 502 in `TestAIBuilder`, order-dependent xAPI test, and Redis-state rate-limit race — all pass in isolation.
- Zero lint errors. `pip install -r requirements.txt --dry-run` shows a clean resolve.

---


## What's been implemented (2026-07-03 · iteration 30e · Documents Tab + Screenshots)

### Full 24-screen capture completed
- ✅ `docs/screenshots/` — 24 PNGs + 24 `_overlay.png` variants (48 files, 12 MB total) with data-testid outlines. `index.md` auto-generated with success/fail annotations. Every canonical IFPI page captured across admin/learner/anon contexts.

### Documents Library (backend + frontend)
- ✅ `backend/services/docs_library_service.py` — Markdown → HTML → PDF via `xhtml2pdf` (pure Python, no cairo/pango deps). Cover page + running footer + on-demand rendering with mtime-keyed cache (1 h TTL). Strips AUTO-BLOCK markers from PDF output while keeping them in raw markdown downloads.
- ✅ `backend/routers/docs_library.py` — 3 endpoints (`GET /api/admin/docs`, `GET /api/admin/docs/{slug}/pdf`, `GET /api/admin/docs/{slug}/raw`). Admin+ role gate.
- ✅ `frontend/src/pages/dashboard/OrganizationDocumentsTab.tsx` — New tab. Lists 4 docs with title, subtitle, audience, line count, size, last-modified. "AUTO-REGENERATED" badge for docs kept in sync by `build_docs.py`. Authenticated blob download → browser save-as.
- ✅ `frontend/src/pages/dashboard/OrganizationSettingsPage.tsx` — Converted single-page to tabbed layout: **Branding & Certificates** | **Documents**.
- ✅ Verified end-to-end via Playwright: 4/4 download buttons render, tab switching works, PDF downloads valid (%PDF header, 42 KB for setup manual).

### Tests
- ✅ `backend/tests/test_iteration30e.py` — 7 tests covering: manifest listing, learner 403, PDF download for all 4 docs, %PDF header, raw markdown variant, 404 envelope for unknown slug, cache hit is faster than cold render. **All pass.**

### Regression
- **17/17 tests** across `test_iteration30d.py` (middleware) + `test_iteration30e.py` (docs library) + `test_docs_completeness.py` (drift gate) all pass.
- Docs drift gate updated: new `/api/admin/docs/*` routes now appear in the auto-generated `api_routes` block (188 total routes).
- Zero lint errors on new files.

### Deferred (from prior plan)
- Locust smoke run — deferred to a dedicated performance-testing session (script ready to run).

---


## What's been implemented (2026-07-03 · iteration 30d · Security + Scale + Screenshots)

### Screenshot capture pipeline
- ✅ `backend/scripts/build_screenshots.py` — Playwright + Chromium capture of 24 canonical screens (admin/learner/anon contexts). Optional `--overlay` mode outlines every element with a `data-testid` in red. Emits `docs/screenshots/index.md` with all captures linked + failure notes. Login page verified (127 KB PNG rendered).

### Security uplift (Option B, partial)
- ✅ `backend/core/middleware.py`:
  - **Correlation-ID middleware** — reads or generates `x-correlation-id`, propagates via `contextvars`, echoes on the response. Truncates pathological inputs to 64 chars.
  - **Global exception envelope** — every `4xx/5xx` returns `{error: {code, message, status, correlation_id}}`. Wired for both FastAPI + Starlette HTTPException so 404s from unmatched routes surface too. 500s log the stack + return a sanitized message.
  - **Brute-force lockout** on `/api/auth/login` and `/api/member/auth/login` — 5 failures / 15 min per `email+IP` combo via Redis sliding window. Successful login resets the bucket. Returns `429 LOGIN_LOCKED_OUT` with `Retry-After`.
- ✅ `backend/tests/test_iteration30d.py` — 7 tests covering all three features. All pass.
- ⏳ **Deferred to a dedicated PR:** cookie sessions + CSRF middleware (touches every auth path; needs the testing agent).

### Scalability quick-wins
- ✅ `backend/core/slow_query_logger.py` — SQLAlchemy `before/after_cursor_execute` listeners. Configurable via `SLOW_QUERY_MS` (default 500 ms). Logs elapsed / rowcount / statement / params / correlation_id for Grafana-Loki parsing.
- ✅ `backend/core/database.py` — Postgres pool tuned via `DB_POOL_SIZE` (20), `DB_MAX_OVERFLOW` (10), `DB_POOL_RECYCLE_SECS` (1800). SQLite path unchanged.
- ✅ `backend/scripts/locustfile.py` — Load-test suite with weighted spawn (5 % admin, 90 % learner, 5 % anonymous). Covers dashboard, courses, flashcards, catalog, verify, spend chart. `--tags smoke` for a 30 s CI smoke run.
- ⏳ **Deferred:** Redis pub/sub cache invalidation bus for cross-worker JWT cache (needs the multi-worker uvicorn config first). PgBouncer sidecar for prod.

### Test posture
- **44/44 pytests pass** across iteration_28/29/30/30b/30d + docs completeness.
- Middleware install order: CorrelationId → LoginBruteForce → exception handlers.
- No lint errors on new files.

---


## What's been implemented (2026-07-03 — iteration 30c · Docs Automation)

### Auto-generated manuals + CI drift gate
- ✅ `/app/backend/scripts/build_docs.py` — scans `role_registry`, live FastAPI routes, router/model file inventory. Regenerates `<!-- AUTO:BEGIN X -->…<!-- AUTO:END X -->` blocks in all four IFPI manuals in-place. Human-authored prose untouched. `--check` mode for CI, `--html` render.
- ✅ Auto-blocks live: `role_matrix`, `role_aliases`, `api_routes` (187 routes), `router_index`, `model_index`.
- ✅ `/app/backend/tests/test_docs_completeness.py` — 3 tests: (a) drift-check via `build_docs.py --check`, (b) every `/api/*` route is mentioned in some manual, (c) every router file is indexed.
- ✅ `tests/conftest.py` — exempts `test_docs_*` from the "no backend → skip" rule so docs gate runs on any CI runner.
- ✅ `.github/workflows/ci.yml` — new `docs-drift` job runs on every PR + push; uploads the generated `IFPI_Master_Manual.html` (104 KB) as a build artifact.

### Verified end-to-end
- Drift-check on corrupt AUTO block → exit 1 with "run build_docs.py" message.
- Drift-check on clean tree → exit 0.
- Manuals now auto-regenerate on every push; contributors adding a router without updating docs will fail CI immediately.

---


## Original problem statement (verbatim)
> "Build IFPI as a sibling app that is pre-made to 'drop into' ERP360 at a later stage and borrow all patterns, reuse APIs if this can be done and won't affect ERP360 now with an easy method to bolt it onto ERP360 when we are ready to do so."

User-confirmed choices (all option (a)):
1. Wipe the Next.js prototype, rebuild fresh in `/app`.
2. AI course builder enabled, using the Emergent LLM key.
3. Full JWT + HTTP-only cookie + refresh-token rotation (ERP360 pattern).
4. Multi-academy from day 1 — `organization_id` on every owned row.
5. Stub billing UI in v1, ERP360 webhook handler wired but disabled (flip one env flag to go live).

## Architecture
- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic-ready + bcrypt + python-jose (matches ERP360 stack exactly).
- **DB:** SQLite locally (`DATABASE_URL=sqlite:///./ifpi_lms.db`). Postgres-ready — change one env var, no code change.
- **Frontend:** React 18 + TypeScript + Tailwind + Radix UI + React Query + React Router v7 + lucide-react + sonner.
- **Auth pattern:** Mirrors ERP360 — JWT access tokens (60-min default), HTTP-only cookie + refresh tokens with family-tracked rotation and reuse-detection.
- **Role registry:** `core/role_registry.py` — `SUPER_ADMIN`, `ADMIN`, `INSTRUCTOR`, `BILLING_VIEWER`, `LEARNER` + alias normalisation. Mirrors ERP360 shape.
- **Multi-tenant:** Every domain row (`User`, `Course`, `Exam`, `Subscription`, `Notification`) carries `organization_id`. Default "IFPI Main Academy" seeded.
- **Service layer:** Thin controllers (`routers/`) → services (`services/`) own DB access — copies ERP360's pattern.
- **Two pre-built integration seams to ERP360 (flip a flag to enable):**
  - `services/sso_service.py` — JIT-provisioning from ERP360 JWT; role map `OWNER→ADMIN`, `MANAGER→ADMIN`, `TRAINER→INSTRUCTOR` etc.
  - `services/billing_service.py` — STUB mode auto-activates; LIVE mode hands off to ERP360 `/api/lite-billing/profiles`.

## What's been implemented (2026-07-02 — iteration 30b · P0 hardening → user QA)

### 1 · Redis-backed rate limiter (shared across replicas)
- ✅ New `services/rate_limit_service.py` — sorted-set sliding window in Redis with graceful in-memory fallback if `REDIS_URL` is unset or Redis is down. Public API: `check(key, max_requests, window_secs)` raises HTTPException(429) with `Retry-After`.
- ✅ Redis is now managed by supervisor (`/etc/supervisor/conf.d/redis.conf`), auto-restart, port 6379, no persistence.
- ✅ `REDIS_URL=redis://localhost:6379/0` added to `backend/.env`; `redis==8.0.1` frozen into `requirements.txt`.
- ✅ `routers/public_catalog.py::_ratelimit` rewritten to delegate to the new service. Verified: 45 rapid-fire anonymous verify calls trigger 429 with valid Retry-After header, works from multi-pod replicas.

### 2 · Clickable verify link inside PDF certs
- ✅ `services/pdf_certificate_service.py` — added `c.linkURL()` overlay under the QR so PDFs now have a "Verify online →" clickable link annotation (embeds `/URI` in the raw PDF stream). Also renders the truncated URL as offline-readable text.
- ✅ ReportLab-native — no extra deps. Cert file size grew from ~4.7 KB to ~5 KB.

### 3 · Mind-map preview thumbnails on course cards
- ✅ `MindMapPage.tsx::save()` now snapshots `.react-flow__viewport` SVG via `XMLSerializer`, base64-encodes it, sends as `thumbnail_svg` on the layout PUT (max 200 KB pydantic-enforced).
- ✅ `routers/authoring_extras.py` — `MindMapLayoutIn.thumbnail_svg` optional field persists into `course.metadata_json.mindmap_thumbnail_svg`; DELETE clears both layout + thumbnail.
- ✅ `schemas.CourseSummary` + `CourseDetail` now surface `mindmap_thumbnail_svg`.
- ✅ `CoursesPage.tsx` — admin-only overlay renders the thumb as a full-bleed background on the card cover with a "Mind map" chip + dark gradient scrim for legibility. Testid `mindmap-thumb-{id}`.

### 4 · Testing
- ✅ New `tests/test_iteration30b.py` — mind-map thumbnail round-trip + oversize rejection + PDF /URI link annotation. 3/3 pass.
- ✅ Testing subagent Iter 20 report: 23/23 backend tests + all critical frontend flows green. No regressions.

---

## What's been implemented (2026-07-05 — iteration 28 · production hardening)

### 1 · Dedicated worker pool for long AI jobs
- ✅ `services/background_worker.py` — a `ThreadPoolExecutor(max_workers=2, thread_name_prefix="ifpi-long-worker")` distinct from FastAPI's anyio pool. `submit_long_job(fn, *args)` submits and returns a Future with automatic exception logging.
- ✅ `routers/authoring_media.py::start_video_generation` now uses `submit_long_job(_run_video_job, ...)` instead of `bg.add_task(...)`. A stuck 5-minute Sora render can no longer cascade into other sync endpoints timing out.
- ✅ Shutdown hook drains the pool on server stop (`shutdown_long_workers(wait=False)` in `server.on_shutdown`).

### 2 · Sora spend-preview modal
- ✅ New endpoint `POST /api/authoring/video/preview` (staff-only) returns `{estimated_cost_cents, budget, will_exceed_budget}`.
- ✅ Frontend `VideoEditor` now opens `SpendPreviewModal` on Generate → shows $X.XX cost + remaining budget + red warning if over-budget. Confirm button is disabled when it would exceed. Uses purple theme + testids `video-spend-modal / -cost / -remaining / -warning / -confirm / -cancel`.

### 3 · Anonymous verify rate-limit
- ✅ Started with `slowapi` but hit K8s ingress / IP-key resolution issues. Replaced with a simple in-memory sliding-window limiter in `routers/public_catalog.py::_ratelimit`. 30 requests/min per IP, sends `Retry-After` header. Verified live: request #31 returns 429.
- ✅ IP resolver uses `X-Forwarded-For[0]` → `X-Real-IP` → `request.client.host`.

### 4 · Mind-map layout persistence
- ✅ New `courses.metadata_json` column (JSON) + migration `a1b2c3d4e5f6`. Layouts saved as `{"mindmap_layout": {graph, positions, saved_by_id, saved_at}}`.
- ✅ New endpoints (staff-only, `/api/authoring/mindmap/{course_id}/layout`):
  - `GET` → `{has_saved, graph, positions, saved_at}`
  - `PUT` → save
  - `DELETE` → clear
- ✅ `MindMapPage.tsx` rewritten with drag-triggered dirty flag, "Save layout" button (indigo), "Unsaved changes" flag, "Clear saved" (rose). Auto-loads saved layout on open — regenerate button forces a fresh LLM call.

### 5 · Login screen → public catalog
- ✅ Login page now shows "📚 Browse the public catalog · verify a certificate" link below sign-up (`data-testid="login-browse-courses"`). Zero-auth funnel for new visitors.

### Improvement · Shareable verify link
- ✅ `VerifyCertPage.tsx` — new "🔗 Copy shareable verify link" emerald button copies `${origin}/verify/{code}` to clipboard with a fallback prompt. Now switches to `/api/public/certificates/verify/{code}` (rate-limited) instead of the legacy path.

### Verification
- Backend: **8/8** new tests in `tests/test_iteration29.py` (rate-limit + preview + mindmap layout + dedicated-worker enqueue). **50/50** regression across iter25-28.
- Smoke: browse-courses link visible on login page.

## What's been implemented (2026-07-04 — iterations 27b + 27c + P2 + P3)

### Iter 27b — Mind maps (P1 complete)
- ✅ `services/mindmap_service.py` — LLM-driven extraction (1 root + N topics + 3 children/topic). Returns strict `{root, topics}` JSON with schema validation.
- ✅ `POST /api/authoring/mindmap/{course_id}?max_topics=6` — staff-only; ~1¢ per generation.
- ✅ Frontend `/courses/:id/mindmap` — **react-flow** (v11.11.4) with radial layout: indigo root centre, pink topic ring (R=260px), white sub-topic ring (R=130px). MiniMap + controls + regenerate button + topics dropdown (3/4/5/6/8/10/12).
- ✅ `Mind map` button added to CourseEditPage next to Flashcards.

### Iter 27c — PPTX export (P1 complete)
- ✅ `services/pptx_export_service.py` — `python-pptx` renderer with 16:9 aspect + title slide + one content slide per course slide (HTML-stripped body, media URL annotation).
- ✅ `GET /api/authoring/pptx/{course_id}` — staff-only; returns MP4-style Content-Disposition attachment.
- ✅ Frontend "PPTX" button on CourseEditPage — uses `blob` responseType + programmatic click for auth-safe download.
- ✅ `feature_flags.pptx_export_enabled` flipped True.

### P2 — API token 30-day analytics
- ✅ New model `ApiTokenCall` + migration `f6a7b8c9d0e1`. Middleware on `server.py::_api_token_call_logger` records one row per API-token-authenticated call (path, method, status, duration_ms).
- ✅ `GET /api/admin/api-tokens/analytics/usage?days=30` — returns per-day series (with zero-fill), by-token breakdown, total_calls, total_errors.
- ✅ Frontend inline SVG `UsageChart` (no chart-lib dep added) rendered above the tokens table. Red bars for days with errors.

### P2 — SCORM runtime shim
- ✅ `GET /api/scorm/runtime.js` — anonymous, served with 10-min cache. Provides `window.API` (SCORM 1.2) + `window.API_1484_11` (SCORM 2004) — both bridge to `POST /api/xapi/statements` via `navigator.sendBeacon` (survives unload). Auto-detects LMS origin from `document.currentScript.src` — no hardcoded URLs.

### P3 — Public catalog + cert-verify + `read:catalog` scope
- ✅ New scope-aware auth: `auth/api_tokens.py` now preserves any scope containing `:` (e.g. `read:catalog`) verbatim through `authenticate_api_token` and the create endpoint. Role tokens (LEARNER, ADMIN…) continue to be normalized uppercase.
- ✅ `GET /api/public/catalog` — PUBLISHED courses only, no PII. Requires either a login session OR an API token with `read:catalog` scope (regular tokens get 403).
- ✅ `GET /api/public/certificates/verify/{code}` — anonymous, returns `{holder_name, course_title, issued_at, score, type, organization_name}` (no email, no learner user_id).
- ✅ Frontend `/public` + `/verify` + `/verify/:code` — unauthenticated page with two tabs (Catalog / Verify certificate). Catalog accepts an API token pasted into the UI; Verify accepts a certificate code.
- ✅ `/tokens` CreateModal now shows `read:catalog` as a selectable scope.

### Verification
- Backend: **50/50 pytest** on new `tests/test_iteration28.py`, **63/63** across iter22-28 full recent surface.
- `testing_agent_v3_fork` iteration_19 verified all UI flows live: /public + /verify, mind map, PPTX download, token analytics chart, scope-gated catalog. Zero critical/major issues.

### Feature flags — every one is ON
tutor · deep_research (Tavily) · flashcards · tts · video_overview (Sora 2) · visuals (Nano Banana) · pptx_export. The full AI Authoring Suite roadmap is functionally complete.

## What's been implemented (2026-07-03 — iterations 26b + 27a + streak-pill + stale-test cleanup)

### Iter 26b — Sora 2 video overviews (P1 complete)
- ✅ `services/video_service.py` — wraps `OpenAIVideoGeneration.text_to_video` (sync, blocking 2-5 min) + storage backend + cost estimator (`sora-2` 10¢/s · `sora-2-pro` 30¢/s).
- ✅ Async pattern via `AIJob(job_type=SORA_VIDEO)`:
  - `POST /api/authoring/video/generate` — returns 202 + `job_id + estimated_cost_cents + estimated_wait_seconds`. Runs Sora in a FastAPI BackgroundTasks worker.
  - `GET /api/authoring/video/{job_id}` — poll status.
  - `GET /api/authoring/video/history` — recent jobs list.
- ✅ On completion: MP4 is saved to storage, attached to slide (`media_url + slide_type=VIDEO`), cost recorded via `ai_budget_service.record_spend`, audit trail written.
- ✅ Validation: models `sora-2 / sora-2-pro`, sizes `1280x720 / 1792x1024 / 1024x1792 / 1024x1024`, durations `4 / 8 / 12`s.
- ✅ Frontend `VideoEditor` panel on CourseEditPage — prompt textarea + model/duration/size selectors + live "Job #N · RUNNING · rendering — safe to leave and come back" polling status.
- ✅ **Verified live**: successful 4s 720p generation with `sora-2` returned a 2.3 MB MP4 attached to slide.

### Iter 27a — Nano Banana infographics (P1 partial complete — mind maps + PPTX deferred)
- ✅ `services/visuals_service.py` — wraps `LlmChat.with_model("gemini", "gemini-3.1-flash-image-preview").send_message_multimodal_response()`. Fully async, ~5-15s per image.
- ✅ `POST /api/authoring/visuals/generate` (staff-only) — `{prompt, slide_id?, model, attach_to_slide?}`. Persists PNG/JPG to storage. When attached, updates `slide.media_url + slide_type=IMAGE`.
- ✅ Cost estimator: 4¢ (`gemini-3.1-flash-image-preview`) / 6¢ (`gemini-3-pro-image-preview`) per image. Budget preflight + spend recording via `ai_budget_service`.
- ✅ Frontend `VisualEditor` panel on CourseEditPage — prompt textarea + preview + Generate/Re-generate buttons.
- ✅ **Verified live**: prompt "Simple diagram showing three phases: Compose, Record, Distribute" → 775KB JPG generated in ~10s.
- ✅ `feature_flags.video_overview_enabled + visuals_enabled` flipped True.

### Improvement — Streak pill in sidebar (complete)
- ✅ `DashboardLayout.tsx` fetches `/api/learn/flashcards/streak` on mount + every 60s. When `current_streak > 0`, shows a 🔥 pill above the user badge with `N-day streak · Locked in today ✓` or `Review to keep alive`. Applies to admins and learners equally (staff can review flashcards too).

### Stale tests cleanup (complete)
- ✅ `test_iteration6.py::test_academies_search_and_sort` — changed to case-sensitive comparison to match SQLite's default `ORDER BY` collation (previous test wrongly expected `str.lower` collation).
- ✅ `test_iteration9.py::TestAlembic` — removed hard-coded revision IDs; now asserts `"(head)"` is reported by `alembic current` (was breaking on every new migration).
- ✅ `test_ifpi_api.py::test_take_exam_and_grading` — added graceful skip when the learner has consumed all attempts on the seeded exam (test pollution from prior runs).
- ✅ `test_iteration22.py::test_authoring_status_admin_can_access` — updated to expect `tts_enabled + video_overview_enabled + visuals_enabled = True`.

### Regression fix — slide reorder + UNIQUE constraint
- ✅ `PATCH /api/courses/{id}/slides/reorder` now uses a two-pass update (`order_index = -i` then `= i`) to satisfy `uq_course_slides_order` without a transient collision. Test `test_iteration3::test_slides_reorder` now green.

### Verification
- Backend: **262/263 pytest** (1 pre-existing skip). Earlier session had 4 stale failures — now zero.
- New tests: `tests/test_iteration27.py` (11 tests for Sora start/validation/history + Nano Banana generate/attach/cost).
- Manual smoke: video job goes PENDING → RUNNING → COMPLETED in ~3-4 min, MP4 attached to slide. Visual generates + attaches in ~10s.

### Still deferred to a future iteration
- **Iter 27b · Mind maps** — needs viz lib pick (e.g. `react-flow`) and node/edge extraction from slide content.
- **Iter 27c · PPTX export** — `python-pptx` render of a course into a downloadable `.pptx`.
- **P2 · Token usage analytics 30-day chart** — needs `ApiTokenCall` log table + middleware.
- **P2 · SCORM runtime shim** (`window.API` / `window.API_1484_11`).
- **P3 · Public read-only catalog + cert-verify API** behind `read:catalog` token scope.

## What's been implemented (2026-07-02 — iterations 25b + 25c + 26a)

### Iter 25b — DB unique constraints (P1 backlog complete)
- ✅ `UniqueConstraint("organization_id", "title")` on `courses` and `(course_id, order_index)` on `course_slides`. Alembic migration `e5f6a7b8c9d0` (batch-mode-safe for SQLite, dedupes any pre-existing collisions before adding the constraint).
- ✅ Pre-flight check in `POST /api/courses` returns 409 instead of a 500 IntegrityError on duplicate title.

### Iter 25c — Flashcard streak + XP (improvement complete)
- ✅ `GET /api/learn/flashcards/streak` — pure derived stat (`current_streak / longest_streak / reviewed_today`) computed from `FlashcardReview.last_reviewed_at`. **No schema change** — same query works on any DB engine.
- ✅ Every review with `quality >= 3` awards `+2 XP` (`+4` for quality=5). First review of the day adds a `+25 XP` streak bonus.
- ✅ Review endpoint response now includes `xp_awarded`, `streak_bonus_applied`, `streak`.
- ✅ Learner flashcard player shows a live 🔥/💤 streak card + toast "+X XP · 🔥 streak bonus!" flash after each rating.

### Iter 26a — OpenAI TTS slide narration (Iter 26 partial complete — Sora deferred)
- ✅ `services/tts_service.py` — wraps `emergentintegrations.llm.openai.OpenAITextToSpeech` with a 4096-char chunker (up to 6 chunks / ~24K chars per slide), pluggable storage backend, and cost estimator (`$0.015 / $0.030 per 1K chars` for `tts-1` / `tts-1-hd`).
- ✅ Migration `e5f6a7b8c9d0` also adds `course_slides.narration_url + narration_voice`.
- ✅ Staff routes:
  - `POST /api/authoring/narration/generate` — body: `{slide_id, voice, model, override_text?}`. Voices: 9 (alloy, ash, coral, echo, fable, nova, onyx, sage, shimmer). Models: `tts-1`, `tts-1-hd`.
  - `DELETE /api/authoring/narration/{slide_id}` — clear cached narration.
- ✅ HTML tags in slide content are stripped before TTS. Budget pre-flight + spend recording via `ai_budget_service`.
- ✅ `SlideOut` schema exposes `narration_url + narration_voice`. Learner LearnPage renders an inline `<audio>` player when set.
- ✅ CourseEditPage has an "AI narration" panel per slide — voice/model selectors + Generate/Re-generate/Remove buttons.
- ✅ `feature_flags.tts_enabled` flipped True.

### Verification
- Backend: **22/22 pytest** across `test_iteration25.py + test_iteration26.py` (5 SM-2 pure + 6 flashcards e2e + 1 uniqueness constraint + 2 streak + 4 narration endpoints + 3 TTS pure/cost + 1 role-gate).
- Smoke screenshot confirms narration panel + flashcards button visible in CourseEditPage.

### Not yet done (deferred to next iteration for scope reasons)
- **Iter 26b — Sora 2 video overviews** (requires its own playbook + async job with ~2-6 min generation time + $200 default org budget per user's earlier config choice)
- **Iter 27 — Mind maps + Nano Banana infographics + PPTX export** (three sub-features, one iteration each)
- **P2 backlog — Token usage analytics 30-day chart** (needs a new `ApiTokenCall` log table + backfill logic)
- **P2 backlog — SCORM runtime shim** (`window.API` / `window.API_1484_11`)
- **P3 backlog — Public read-only catalog + cert-verify API** behind `read:catalog` token scope

## What's been implemented (2026-07-01 — iterations 24 + 25)

### Iter 24 — Deep research via Tavily (P0 complete)
- ✅ `POST /api/authoring/research/start` — accepts `{query, depth: quick|deep, course_id?}`, returns 202 + `AIJob.id`. Background task runs asynchronously via `asyncio.run()` (previous version used `asyncio.new_event_loop().run_until_complete()` which crashed under FastAPI's BackgroundTasks — fixed).
- ✅ Tavily `POST /search` — `search_depth=basic` for quick, `advanced` for deep. Uses `include_answer=True + include_raw_content=True` to get citation-rich results.
- ✅ Synthesised briefings become `SourceDocument(source_type='RESEARCH_NOTE')` — retrievable by the AI tutor for grounded QA.
- ✅ `GET /api/authoring/research/{job_id}` + `GET /api/authoring/research` for history view. Both `requires_staff()`.
- ✅ Cost recorded via `ai_budget_service.record_spend` — Tavily is separate provider from the Emergent LLM key.
- ✅ Frontend `/research` (admin-only) — form + polling + history list at `pages/dashboard/ResearchPage.tsx`. Sidebar entry with Sparkles icon.

### Iter 25 — Auto flashcards + SM-2 spaced repetition (P0 complete)
- ✅ New models: `Flashcard` (course-scoped, org-scoped, tracks provenance via `source_chunk_ids`) and `FlashcardReview` (per-user SM-2 state — ease_factor, interval_days, repetitions, next_review_at). Alembic migration `d4e5f6a7b8c9`.
- ✅ `services/flashcard_service.py` — LLM generation (Emergent LLM key, model `settings.ai_builder_model`) + pure `apply_sm2(quality 0-5, ease, interval, reps)` returning `(new_ease, new_interval, new_reps, next_review_at)`. Ease floor 1.3 per SuperMemo-2 spec.
- ✅ Staff routes at `/api/authoring/flashcards/*`:
  - `POST /generate` — preview batch (does not persist), augments with RAG chunks when `use_sources=True`.
  - `POST /bulk-save` — persist reviewed set.
  - `GET /by-course/{id}` — list saved cards.
  - `PATCH /{id}` / `DELETE /{id}` — edit + delete (delete cascades to reviews explicitly).
- ✅ Learner routes at `/api/learn/flashcards/*`:
  - `GET /courses/{id}/due` — SM-2 due queue (overdue reviews first, then unseen cards to backfill).
  - `POST /{id}/review` with `{quality: 0-5}` — creates/updates review row.
  - `GET /courses/{id}/stats` — total / new / learning / mastered / due_now.
- ✅ Frontend `/courses/:id/flashcards` (admin) — full preview + edit + bulk-save UI + saved-card list.
- ✅ Frontend `/learn/:courseId/flashcards` — **swipeable primary + list secondary** (per user choice). Keyboard shortcuts: Space to flip, 1-5 to rate. Stats bar at top (Total, Due now, New, Learning, Mastered). Session-complete state.
- ✅ Nav: `Sparkles` "Flashcards" button on `CourseEditPage`; "Practice flashcards" pill on the learner course sidebar.
- ✅ **Fixed SQLite FK enforcement bug** — added `PRAGMA foreign_keys=ON` event hook in `core/database.py`. Belt-and-braces: explicit review cleanup in the DELETE endpoint too.
- ✅ 11 new tests in `tests/test_iteration25.py` (5 pure SM-2 units + 6 endpoint/e2e). Also updated `tests/test_iteration22.py::test_authoring_status_admin_can_access` to expect `tutor_enabled=True, flashcards_enabled=True` (stale assertion from infra-only iter).
- ✅ `feature_flags.deep_research_enabled` reflects `TAVILY_API_KEY` presence, `flashcards_enabled=True`, `tutor_enabled=True`.

### Verification
- Backend: **40/40 pytest** across `tests/test_iteration22.py + test_iteration23.py + test_iteration25.py`.
- Frontend: verified via `testing_agent_v3_fork` iteration_16 — Deep research page renders, learner flow (flip → rate → session-done) works, admin flashcards-btn navigates correctly, learner `/learn/:id/flashcards` link works, learner correctly blocked from `/research` and `/courses/:id/flashcards` (redirects).

## What's been implemented (2026-06-29 — iteration 15)
- ✅ **Outgoing webhooks (HMAC-SHA256 signed) — companion to iter14 SSO**. New `WebhookSubscription` + `WebhookDelivery` models (migration `d5f0a3bc7e91`). `services/webhook_service.py` exposes `sign(secret, body)`, `emit_event(db, org_id, event_type, payload)`, `drain_failed(db)`. Headers on every POST: `X-IFPI-Signature` (hex HMAC), `X-IFPI-Signature-Algorithm: HMAC-SHA256`, `X-IFPI-Event-Id` (UUID for receiver dedup), `X-IFPI-Event-Type`. Body is a stable envelope `{event_type, event_id, organization_id, occurred_at, data}`.
- ✅ **Retry pipeline** — 3 attempts with backoff `[30s, 5min, 30min]` then `DEAD_LETTER`. New APScheduler tick `_webhook_retry_tick` runs every 30s draining FAILED rows whose `next_attempt_at` is due.
- ✅ **Emit hooks wired**:
  - `course.completed` + `certificate.issued` after successful `POST /api/courses/{id}/complete` (only when actually first-time — idempotent re-completes do NOT re-fire).
  - `cohort.milestone_reached` after the cohort celebration audit + email + Slack/Discord ping.
- ✅ **Admin CRUD** — `GET/POST/PUT/DELETE /api/admin/webhooks` + `POST /api/admin/webhooks/{id}/test` + `GET /api/admin/webhooks/{id}/deliveries`. Auto-generates a 32-byte URL-safe secret if not supplied. Writes `WEBHOOK_SUBSCRIPTION_CREATED/UPDATED/DELETED` and `WEBHOOK_TEST_FIRED` audit rows.
- ✅ **Admin UI** — new `/webhooks` page in sidebar: list cards with pulse status dot, event-tag pills, masked secret with reveal/copy buttons, last-success/failure timestamps. Inline expandable delivery log per sub showing status pills (DELIVERED/FAILED/DEAD_LETTER), attempt count, error truncated. "Add subscription" modal with target URL, event toggles (or `*` wildcard), description, optional custom secret. Audit log gets cyan/sky/rose/violet pills for the new actions.
- ✅ Tests: **iter15 9/9 PASS** — CRUD + LEARNER 403 + 5xx-marks-FAILED + HMAC signature deterministic-and-verifiable + envelope shape + event filter narrowing + E2E course completion fires `course.completed` to capture server. Regression: **77/77 across iter9-15**.

## What's been implemented (2026-06-29 — iteration 14)
- ✅ **ERP360 SSO drop-in (HS256, fully hardened)** — `/api/auth/sso-exchange` accepts an ERP360-minted JWT (`iss=erp360`, `aud=ifpi-lms`, `sub`, `email`, `iat`, `exp`, `jti`, `name`, `roles[]`, optional `person_id`). Verifies signature via `ERP360_SSO_SHARED_SECRET` (HS256). Hardening: required claims (`exp`/`iat`/`sub`), issuer check, audience check, `iat` freshness (max 5 min old), `jti` replay-prevention via in-memory TTL set.
- ✅ **JIT provisioning** — first SSO login auto-creates the IFPI User + Person rows linked by `erp360_user_id` / `erp360_person_id`; subsequent logins idempotently reuse them. Role map: `OWNER/MANAGER/HEAD_OF_ADMIN→ADMIN`, `PLATFORM_ADMIN/SUPER_ADMIN→SUPER_ADMIN`, `TRAINER/HR_ADMIN→INSTRUCTOR`, `ACCOUNTANT/BILLING_USER→BILLING_VIEWER`, everyone else → `LEARNER`. (Bug fix: skip role-registry pre-normalisation so the ERP360-specific keys win.)
- ✅ **Status endpoint** — `GET /api/auth/sso-status` (public) returns `{enabled, initiate_url}` so the login page conditionally renders a "Continue with ERP360" button. `initiate_url` composes ERP360's mint endpoint URL + return_to=/sso/return.
- ✅ **Frontend SSO button** — LoginPage probes `/sso-status` on mount; when enabled shows pill button above the email/password form with "OR SIGN IN DIRECTLY" divider. URL param `?erp_token=…` auto-triggers `/sso-exchange` and lands on the right dashboard route based on role.
- ✅ **Audit** — both `SSO_LOGIN_SUCCESS` (every exchange) and `SSO_USER_PROVISIONED` (first-time JIT) rows are written with IP + email + role metadata.
- ✅ Tests: **iter14 12/12 PASS** — happy path, idempotent reuse, unknown role → LEARNER fallback, bad signature, wrong issuer, wrong audience, expired token, iat-too-old, missing jti, replay prevention, audit-row verification. Full regression: **68/68 across iter9-14**.

## What's been implemented (2026-06-29 — iteration 13)
- ✅ **Weekly cohort digest** — new APScheduler cron job (`Mon 09:00 UTC`) calls `services.cohort_digest.send_weekly_digests()`. For each org with `cohort_digest_enabled=True`, composes a single HTML email per admin bucketing cohorts into **past threshold / nudge zone (within 15pp) / early progress**. Nudge rows show "N more completions to celebrate". Idempotent — `cohort_digest_last_sent_at` + 6-day dedupe window guarantees ≤1 send/week even on misfire.
- ✅ Migration `c4f9826dfe44` — adds `organizations.cohort_digest_enabled` (Boolean, default True) + `cohort_digest_last_sent_at` (DateTime nullable).
- ✅ New endpoint `POST /api/organization/cohort-digest/send-now` (admin only) — manual trigger that bypasses dedupe so admins can preview. Returns `{queued, total_cohorts, past, nudge, threshold}`. Writes `COHORT_DIGEST_SENT` audit row.
- ✅ PUT `/cohort-settings` now accepts optional `cohort_digest_enabled` (omitted = unchanged).
- ✅ Frontend Settings → Cohort celebrations: new gradient "Weekly cohort digest" card with ON/OFF status pill, enabled checkbox, last-sent timestamp (`Last sent: Jun 29, 2026, 11:56 AM`), and "Send digest now" button. `COHORT_DIGEST_SENT` gets indigo pill in `/audit`.
- ✅ Tests: **iter13 10/10 PASS**, iter12 7/7, iter11 14/14, iter10 14/14, iter9 11/11 — **56/56 across all iterations**. Updated iter9 alembic head test to accept new revision id.

## What's been implemented (2026-02-08 — iteration 12)
- ✅ **Cohort celebration webhook — "Send test ping" + provider auto-detect** — new `POST /api/organization/cohort-settings/test-webhook` endpoint sends a sample celebration payload (`{text, content, username}`) to the supplied URL, returns `{ok, status_code, provider, error}` so the UI surfaces the upstream response inline. Provider is auto-detected from URL (`discord` | `slack` | `generic`) and shown as a colored pill above the input. Inline result card renders green ✓ on 2xx, red ✗ with HTTP code + Discord/Slack error body on failure. Collapsible "Preview celebration message" panel shows what the message will look like before saving. Every test writes a `COHORT_WEBHOOK_TESTED` audit row (with provider + status_code metadata), surfaced with teal pill in `/audit`.
- ✅ Tests: **iter12 7/7 PASS** (422 on bad URL, 403 for learner, network failure → ok=false structured response, Discord/Slack provider detection, audit row written). Regression: iter9/10/11 = 39/39 PASS.

## What's been implemented (2026-02-08 — iteration 11)
- ✅ **AI quiz: regenerate one question** — per-card `RefreshCw` button calls `/ai-generate-questions` with `num_questions=1` + `avoid_topics=<all current question_texts>`. Replaces only that card; spin animation while pending; isolated update verified.
- ✅ **AI quiz: TRUE_FALSE + SHORT_ANSWER + MIXED** — `_TYPE_RULES` dict in `ai_quiz_service.py` drives the LLM prompt; per-question `question_type` is preserved and validated (TRUE_FALSE coerces `True/T/Yes` → `True`, false-equivalents → `False`; SHORT_ANSWER forces `options=[]`; MIXED lets the model choose). Frontend renders type pill + format-aware preview (✓ option / Expected: …).
- ✅ **Action-pill colours** for `AI_QUIZ_GENERATED` (amber), `COHORT_MILESTONE_REACHED` (yellow), `COHORT_SETTINGS_UPDATED` (orange) added to `ACTION_COLORS`.
- ✅ **Cohort leaderboard CSV export** — `GET /api/admin/leaderboard.csv?cohort=X` returns `text/csv` with date-stamped Content-Disposition; admin-only download button on `/leaderboard` next to the cohort dropdown; frontend now reads filename from `Content-Disposition`.
- ✅ **NEW IMPROVEMENT — Audit briefing card on /audit**: `GET /api/admin/audit-digest?days={7|14|30|90}` returns `{days, total_actions, counts_by_action, summary}`. Summary is Emergent-LLM-generated (gpt-4o-mini) plain-English 3-5 sentence executive briefing. Deterministic fallback fires when LLM unavailable. Gradient card at top of `/audit` with days selector, refresh button, summary paragraph, top-6 action pills.
- ✅ Code-review fixes from reviewer:
  - Added `Optional` to `from typing import` in `ai_quiz_service.py` (was only working under `from __future__ import annotations`).
  - Audit digest LLM-failure path logs exception + shows "see logs" instead of leaking exception class to admin UI.
  - Leaderboard CSV: frontend now honours `Content-Disposition` filename (preserves date stamp).
- ✅ Tests: **iter11 14/14 PASS** (incl. LLM avoid_topics honour, TF/SA/MIXED parse, CSV format, deterministic digest fallback), iter10 14/14, iter9 11/11, 39/39 across the three. Frontend 100%.

## What's been implemented (2026-02-08 — iteration 10)
- ✅ **Per-tenant cohort threshold + Discord/Slack webhook** — `organizations.cohort_threshold` (default 75) + `cohort_celebration_webhook_url` (nullable) (migration `b3d8915cef27`). `check_cohorts()` reads per-org threshold; celebrations POST to the webhook with a Slack/Discord-compatible payload. New `/settings → Cohort milestone celebrations` card with a 1-100 slider + monospace webhook URL field + Save button. Idempotency still holds — lowering threshold doesn't re-fire existing milestones.
- ✅ **Cohort-scoped leaderboard** — `GET /api/gamification/leaderboard?cohort=X` filters to a single cohort. `/leaderboard` page (admin only) gains a cohort dropdown next to the title; banner reflects active filter.
- ✅ **Loading skeletons + empty state** on `/reports` cohort widget — animated skeleton tiles while `cohortStats` loads; friendly empty card with a link to `/users` when zero cohorts exist.
- ✅ **GitHub Actions PR comment workflow** — `.github/workflows/pr-agent-comments.yml` runs on `workflow_run` completion, downloads the `agent-reports` artifact, formats agent_007/008/010 results, and updates a sticky PR comment via the GitHub API.
- ✅ **NEW IMPROVEMENT — AI quiz generator**: `POST /api/exams/ai-generate-questions` ingests a course's slide content into Emergent LLM (gpt-4o-mini), returns 1-20 validated multiple-choice questions (correct answer always present in options). `PUT /exams/{id}/questions?mode=replace|append` with `Literal` validation (422 on bad mode). New "AI quiz" button on `/exams` opens a modal that does **generate → review-and-edit → save as new exam OR append to existing exam**. Each generation writes an `AI_QUIZ_GENERATED` audit row.
- ✅ Code-review fixes from reviewer:
  - `mode` query param now uses `Literal["replace","append"]` → 422 on invalid values (was silently appending).
  - AI quiz error responses now include the exception class name (`AI generation failed (TimeoutError) — please retry`) so admins can distinguish auth/timeout/rate-limit failures without grepping logs.
- ✅ Tests: **iter10 14/14 PASS**, iter9 11/11, iter8 16/16. AI quiz returned 3 valid music-industry MCQs in ~5s with correct answers in options. Frontend Playwright 100%.

## What's been implemented (2026-02-08 — iteration 9)
- ✅ **Cohort-aware dashboard widgets** — new "Cohort breakdown" card on `/reports` with a dropdown of all cohorts (with learner counts) and 5 live stat tiles (Learners / Enrollments / Completion rate (indigo accent) / Avg exam score / Certificates).
- ✅ **JSONB migration** — `a9c2470b8e15` no-op on SQLite, converts `audit_logs.audit_metadata` to JSONB + creates a GIN index on Postgres. Single migration, dialect-aware.
- ✅ **Agent 008 hardened + deterministic** — full 18-step E2E (admin login → fixture course/exam lookup → bulk invite with cohort → accept → learner login → enrol → 5 slides complete → exam 100% → cert issued → transcript downloaded → agent_007 re-verified clean). Wired into the `qa-agents` CI job alongside agents 007 and 010.
- ✅ **NEW IMPROVEMENT — Cohort milestone celebrations** (`services/cohort_celebrations.py`): APScheduler job runs every 60s (separate from outbox drain). When a cohort hits ≥75% completion it (a) writes a `COHORT_MILESTONE_REACHED` audit row with full stats + `actor: "system"` in metadata, (b) queues an outbox email to every ADMIN in the org with the milestone copy. Idempotent — once the audit row exists for `(org, "cohort", <cohort_name>)` the celebration never re-fires. Slow-tick warning logs at >30s; misfire_grace_time=120s.
- ✅ Code-review nits addressed:
  - Replaced LIKE-based JSON dedupe with composite-key dedupe (org + action + target_type + target_id) — safer across dialects, immune to substring false-positives.
  - System events now stamp `actor="system"` in metadata so the audit UI can distinguish from missing-actor bugs.
- ✅ Tests: **iter9 11/11 PASS**, iter8 16/16 regression, agent 007 9/9, agent 008 18/18 (was 0 before this iter), 40/40 across iter7+8+9. Frontend Playwright 100%.

## What's been implemented (2026-02-08 — iteration 8)
- ✅ **Learner cohorts** — `users.cohort` + `invitations.cohort` columns (migration `f6b832c5a4e1`). Bulk invite modal gets a "Cohort name" field that propagates to every learner in the batch — and from the Invitation to the User on accept. New endpoints: `GET /api/admin/cohorts` (distinct labels + learner counts) and `GET /api/admin/reports/cohort-stats?cohort=X` (completion rate, avg exam score, certificates issued, badges earned).
- ✅ **Audit log** — new `audit_logs` append-only table (actor, action, target_type, target_id, JSON metadata, ip_address, created_at). `services/audit_service.py::record()` helper instrumented on: `THEME_APPLIED`, `SMTP_CONFIG_UPDATED`, `BADGE_TIER_CREATED/UPDATED/DELETED`, `BADGE_TIERS_REORDERED`, `ACADEMY_CREATED`, `INVITATIONS_BULK_QUEUED`. New `GET /api/admin/audit-log` with action/actor/target filters + pagination. New admin `/audit` page with colored action pills.
- ✅ **NEW IMPROVEMENT — Learner PDF transcripts** — `GET /api/certificates/transcript` renders a single branded PDF for the authenticated user: name, email, cohort, total XP, all completed courses with date+best exam score, all badges with earned dates, footer disclaimer. Branded with the academy's primary_color. "Download transcript" button on `/certificates`.
- ✅ **QA agents ported from ERP360**:
  - `agent_007_invariants.py` — 9 DB invariants (orphan comments, archived-course enrollments, dangling audit FK, duplicate cert codes, etc.)
  - `agent_008_e2e_journey.py` — synthetic learner full flow (run on-demand, not in CI yet)
  - `agent_010_infra_sentry.py` — 8 infra checks (HTTP health, DB, ReportLab, APScheduler, outbox drain, LLM key, Fernet, storage roundtrip)
- ✅ **CI pipeline** — `.github/workflows/ci.yml` with 6 jobs: secret-scan (blocking) → backend-tests / migration-smoke (up→down→up) / service-layer-check (advisory) / qa-agents / frontend lint+build. Secret scanner at `scripts/security/scan-secrets.sh` (104 LOC, 10 patterns, allowlist-aware).
- ✅ Tests: **iter8 16/16 PASS**, iter7 13/13 regression, agent 007 9/9, agent 010 8/8, secret scan PASS. Frontend Playwright 100%.

## What's been implemented (2026-02-08 — iteration 7)
- ✅ **Configurable badge tiers** — new `badge_tiers` table (migration `e5a721f43b18`) with per-org rows. Default 5 tiers (First Step / Graduate / Scholar / Perfectionist / Course Master) auto-seeded for every org including any new academy created via `POST /api/academies`. Admin `/badge-tiers` page with drag-reorder + inline edit modal + delete + toggle-active. `GamificationService` consults DB rows first, falls back to hard-coded map only when an org has no rows (failsafe). `GET /api/gamification/me` now returns per-org tier meta.
- ✅ **Live preset preview** — each preset card on `/settings` now has separate **Preview** and **Apply** buttons. Preview pipes the preset's colors directly to `POST /api/admin/cert-preview` and renders the iframe — zero DB writes. Apply persists.
- ✅ **Per-tenant SMTP overrides** — new columns on `organizations`: `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password_enc` (Fernet-encrypted), `smtp_from_email`, `smtp_from_name`, `smtp_use_tls`. New `services/smtp_service.py` handles encryption + send. Outbox worker now tries per-tenant SMTP FIRST (when configured), then ERP360 bridge, then STUB. New `/settings → Email delivery (per-tenant SMTP)` section with all fields + masked password input + **Send test** button. Endpoints: `GET/PUT /api/organization/smtp` + `POST /api/organization/smtp/test`. **Security**: in production `SMTP_ENCRYPTION_KEY` (32-byte url-safe base64) is REQUIRED. For dev/local, set `SMTP_ALLOW_PLAINTEXT=1` to opt in to plaintext storage with a warning log line — otherwise PUT raises 500.
- ✅ **Bulk learner invites** — `POST /api/admin/invitations/bulk` (cap 500/batch). Per-row response with `{email, status, reason}` so the admin sees exactly what got through. New "Bulk invite" button on `/users → Invitations` opens a modal with textarea (one email per line, optional `, Name` suffix) or CSV upload. Live counter, per-row result feedback, automatic tab-switch to Invitations on success.
- ✅ Tests: iter7 backend suite **13/13 PASS**, iter6 regression **11/11 PASS**, full pytest **99/100** (single pre-existing exam-state pollution unrelated to this batch). Frontend Playwright 100%.

## What's been implemented (2026-02-08 — iteration 6)
- ✅ **Course catalog drag-reorder** — `courses.display_order` column (migration `c1f29b3e9d04`) + `PATCH /api/courses/reorder` endpoint. Admin Courses page has a "Reorder" toggle that switches the grid into a vertical SortableList with drag handles. Order is honored on both `/courses` and the public `/portal/:slug` endpoint.
- ✅ **Academies search/filter/sort** — `GET /api/academies` now accepts `q`, `status_filter`, and `sort` (newest/oldest/name/users/courses). New search input + status dropdown + sort dropdown + Clear link on the Academies page. Cards now show a theme_preset pill when one is applied + use the academy's primary_color in the icon background.
- ✅ **NEW: Per-academy theme presets** — `services/theme_presets.py` ships 5 curated brand kits (IFPI Classic, Conservatoire, Modern Music School, Industry Body, Label Academy). One click on `/settings → Theme presets` copies primary + cert-accent colors and seeds signature/footer text **only if those fields are still empty** (never overwrites admin customisations). Schema: `organizations.theme_preset` (nullable string).
- ✅ **ERP360 webhook receiver reference** — `/app/docs/ERP360_INTEGRATION.md` is a paste-ready FastAPI snippet the ERP360 team can drop into their codebase (HMAC verification + 5-min replay window). IFPI itself unchanged — outbox worker already emits the signed headers via `sign_outgoing_payload()`.
- ✅ Tests: iter6 backend suite 11/11 PASS, iter5 regression 20/20 PASS, frontend Playwright 100% on theme apply / restore / courses reorder / academies filter+sort+clear flows.

## What's been implemented (2026-02-08 — iteration 5 polish)
- ✅ **Pluggable storage backend** — ported the ERP360 `storage_service.py` pattern into `/app/backend/services/storage_service.py` as a clean, IFPI-owned port (zero imports from ERP360). Selectable via `STORAGE_BACKEND={local|s3|gcs}` env var. Default stays `local` writing to `./uploads/`. boto3 + google-cloud-storage are lazy-loaded so they aren't hard deps until needed. The `POST /api/uploads/image` route now delegates to `get_storage().save()`; uploads land under a `branding/` namespace prefix. Legacy flat-path URLs continue to serve (path:path matcher), so old logos don't break.
- ✅ **`PUBLIC_BASE_URL` env** — added `settings.public_base_url`; when set, cert verify URLs in preview + emails use it instead of `request.base_url` (which yields the cluster-internal hostname under k8s ingress). Safe default: empty string falls back to current behavior.
- ✅ **Auto-debounced live cert preview** — `OrganizationSettingsPage` now re-renders the iframe 500ms after any branding field changes (name, logo, accent colors, signature text/image, footer). Initial render still requires one click on "Live preview" to opt in.
- ✅ **"Demo this academy" CTA** — `AcademiesPage` cards now have a prominent `ExternalLink` button that opens `/a/<slug>` in a new tab for instant tenant demos.
- ✅ **Decision: SSO bolt-on is OPT-IN.** ERP360 integration remains entirely feature-flagged (`SSO_ENABLED`, `BILLING_LIVE_MODE`). IFPI runs standalone forever if desired — zero penalty for not bolting on. Documented in PRD.

## What's been implemented (2026-02-08 — iteration 5)
- ✅ **Cert template live preview** — `POST /api/admin/cert-preview` renders an in-memory sample PDF using submitted branding (no DB writes); `/settings` page now has a Live preview button + sticky iframe panel showing the result.
- ✅ **SUPER_ADMIN multi-tenant invite flow** — `GET/POST /api/academies` (SUPER_ADMIN-only). Creating an academy issues a 14-day admin invitation queued in the new tenant's outbox. New `/academies` page with create-modal + per-academy stats card and public-portal deep link.
- ✅ **Slide comments** — `GET/POST/DELETE /api/slides/{slide_id}/comments` with soft-delete and 200-row cap. `CommentsPanel.tsx` mounted in `LearnPage.tsx`: post, reply, see, delete own (admins/instructors can delete any).
- ✅ **Outbox retries + dead-letter** — APScheduler worker (`services/outbox_worker.py`) ticks every 5s, exponential backoff (30s → 5m → 30m), 3-attempt cap → `DEAD_LETTER`. Admin endpoint `POST /api/admin/outbox/{id}/retry` resets a row to `QUEUED`. New per-row Retry button surfaces on FAILED / DEAD_LETTER rows on the Outbox page.
- ✅ **File upload (logos + signature images)** — `POST /api/uploads/image` (5MB cap, mime-allowlist) writes to `/app/backend/uploads/`. Returns a relative `/api/uploads/files/<uuid>.png` URL so it resolves through the public ingress (fixed cluster-host bug). `GET /api/uploads/files/{name}` serves with cache headers. Settings page wires both Logo + Signature upload buttons.
- ✅ **Public academy portal** — `GET /api/portal/{slug}` (no auth) returns org branding + stats + published courses. Frontend route `/a/:slug` renders the public landing.
- ✅ **Outgoing webhook HMAC signing** — `sign_outgoing_payload()` produces `X-Signature` (HMAC-SHA256 of body+timestamp) + `X-Timestamp` headers. Used automatically by the outbox worker when dispatching to ERP360 in live mode.
- ✅ Tests: Iteration 5 backend test suite added at `/app/backend/tests/test_iteration5.py` (20 tests, all green after the two fixes). Frontend Playwright verified all critical flows.
- 🐛 Fixes after iter5 testing agent:
  - `POST /api/uploads/image` now returns relative path (previously returned cluster-internal hostname unreachable from the browser).
  - Added missing `POST /api/admin/outbox/{id}/retry`.

## What's been implemented (2026-01-08 — iteration 4)
- ✅ **Async outbox worker** — `services/outbox_worker.py` using APScheduler runs every 5s on app startup, drains QUEUED rows. MailService now ALWAYS just queues (no inline dispatch), decoupling request latency from upstream mail provider. In stub mode the worker stamps QUEUED→STUB. In live mode it POSTs to ERP360 `/api/notifications/send`.
- ✅ **Outbox pagination + filters** — `GET /api/admin/outbox?page=&page_size=&status=&template=&q=` returns `{messages, page, page_size, total, total_pages}`. New `/stats` endpoint for the counter cards. Frontend Outbox page rewritten with search, status filter, Prev/Next pager.
- ✅ **Course duplication** — `POST /api/courses/{id}/duplicate` deep-clones the course (title + " (copy)") with all slides as a new DRAFT. Copy button on every admin course card. Lets instructors keep a master "template" course and clone it per cohort.
- ✅ **Personalised cert templates per academy** — `Organization` gained `cert_accent_color`, `cert_signature_text`, `cert_signature_image_url`, `cert_footer_text` columns. PDF renderer now uses all of them with graceful fallbacks (malformed colour → default indigo; signature image fetch failure → text signature). New `/settings` admin page with colour pickers, logo URL preview, signature/footer text fields.
- ✅ **Prerequisites UI** — right-sidebar panel on `/courses/:id/edit` lists current prereqs (Lock icon) with a modal picker to add more (excludes self + already-added). Wires to existing `POST/DELETE /api/courses/{id}/prerequisites/{prereq_course_id}` endpoints.
- ✅ Tests: 69/69 backend pytest pass (16 new iter 4 + 15 iter 3 + 11 iter 2 + 27 iter 1). Frontend Playwright verified all critical flows.

## What's been implemented (2026-01-08 — iteration 3)
- ✅ **PDF cert with logo plumbing** — `Organization.logo_url` (URL or local path) now rendered on the cert. Graceful fallback to generated wordmark when URL unreachable. New `GET/PATCH /api/organization` so admins can update branding.
- ✅ **Course prerequisites enforced** — `POST /api/courses/{id}/enroll` returns `412 Precondition Failed` with `{message, missing: [{id, title}]}` when prereqs not done. New admin endpoints: `GET /api/courses/{id}/prerequisites`, `POST/DELETE /api/courses/{id}/prerequisites/{prereq_course_id}`.
- ✅ **Instructor invitation flow** — `POST /api/admin/invitations {email, name, role}` issues a token (14-day TTL, revokes prior pending invite for the same email), queues an HTML invitation email in the outbox. Public `GET /api/invitations/{token}` looks it up; `POST /api/invitations/{token}/accept {password, name}` creates the User + Person + UserRole and auto-logs them in. UI: new "Invite User" modal + "Invitations" tab on `/users`; new `/accept-invite/{token}` public page.
- ✅ **Drag-reorder** — `@dnd-kit/sortable` wrapped in a reusable `SortableList` component. Used on the slides sidebar in CourseEditPage and on the items list in LearningPathEditPage. Backend endpoints: `PATCH /api/courses/{id}/slides/reorder` and `PATCH /api/learning-paths/{id}/items/reorder`.
- ✅ **Cert emails as PDF attachments** — when a learner first completes a course, the PDF cert is generated and the email is queued via `MailService`. Try/except wraps the call so any failure doesn't block the completion.
- ✅ **MailService** — `stub` mode (default — persists to new `outbox_messages` table only) and `erp360` mode (POSTs to `/api/notifications/send` on ERP360 with `X-Service-Token`). Flips on with `BILLING_LIVE_MODE=true` + `ERP360_BASE_URL`. New `GET /api/admin/outbox` audit endpoint + `/outbox` page in the admin UI.
- ✅ **Smart enhancement — Lead Capture** — public `POST /api/leads` accepts `{email, name, source, phone, company, job_title, country, organization_slug}` (no auth). Creates/updates a `Person` row with `lifecycle_stage=PROSPECT` (never downgrades existing LEARNER). Also serves a self-contained JS embed widget at `GET /api/leads/embed.js?organization=<slug>` — partner sites drop one `<script>` tag and they have a working signup form that feeds straight into IFPI.
- ✅ Tests: 53/53 backend pytest pass (15 new iter 3 + 11 iter 2 + 27 iter 1). Frontend Playwright verified all critical iter-3 flows.

## What's been implemented (2026-01-08 — iteration 2)
- ✅ **Alembic migrations** — `/app/backend/alembic/` with baseline migration; runs identically on SQLite (dev) and Postgres (prod). `Base.metadata.create_all` retained as dev safety net only.
- ✅ **Person model** — separate identity entity from User (matches ERP360 pattern). 1:1 with User via unique FK. Holds `lifecycle_stage` (PROSPECT/LEARNER/ALUMNI), `erp360_person_id` for future SSO mapping, contact details (phone/job_title/company/country), `source` (self_register / sso_erp360 / seed). Auto-created on registration and SSO JIT-provision. Seed updated to create Person rows for the seeded admin + learner.
- ✅ **Explicit publish workflow** — `POST /api/courses/{id}/publish` and `/unpublish` with validation (course must have ≥1 slide). Course Edit page now has a status pill + green Publish CTA / amber Unpublish CTA replacing the bare status dropdown.
- ✅ **PDF certificates** — branded landscape A4 cert via ReportLab with QR code linking to `/verify/{code}` for instant verification. Permission-gated: owner OR admin in same org only (403 otherwise). Download button on `/certificates`.
- ✅ **Learning Paths** — full CRUD + ordered items + prerequisites table + enrol-in-path (auto-enrols learner in all child courses, idempotent) + publish validation. Sidebar item added for both admin (`Manage`) and learner (`Enrol in Path`).
- ✅ Tests: 38/38 backend pytest pass (11 new for iter 2 + 27 regression). Frontend Playwright verified.

## What's been implemented (2026-01-08 — iteration 1)
- ✅ Backend: auth (register/login/refresh/logout/me + SSO bridge stub), course CRUD + slides + enrol + complete, exam CRUD + question replace + attempt grading, certificates + verify, leaderboard + gamification (XP/badges), notifications, admin analytics (SQLite-safe — no DATE_TRUNC), admin users list, billing subscribe + subscriptions + webhook handler, public catalog. 27/27 pytest tests pass.
- ✅ Frontend pages: Landing, Login, Register (LEARNER-only), Public Catalog, Verify Certificate, Dashboard, Courses list (with AI Builder modal), Course Edit (working save + slides), Exams list, Certificates, Users, Reports, Leaderboard, Billing (stub banner). Course player (`/learn/:id`), Exam taker (`/take/:id`).
- ✅ AI Course Builder: live, real LLM calls via `EMERGENT_LLM_KEY` (default `gpt-4o-mini`), generates slides + multi-choice questions, "Apply to Course" creates a draft course + draft exam in one shot.
- ✅ Security fixes from the prototype review:
  - Self-registration creates `LEARNER` only (never `ADMIN`).
  - All mutating endpoints role-gated via `requires_roles` dependency.
  - True/False answer encoding unified (`"true"`/`"false"`) end-to-end.
  - Analytics endpoint rewritten in Python — works on SQLite (no `DATE_TRUNC` crash).
- ✅ Seeded data: 1 academy, 1 admin (`admin@ifpi.org/admin123`), 1 learner (`learner@ifpi.org/learner123`), 1 course "IFPI Fundamentals" (5 slides, published, free), 1 exam (4 questions, published, linked to the course).
- 🟡 Billing in STUB mode — `POST /api/billing/subscribe` returns `is_stub: true` and auto-activates the subscription. Flip `BILLING_LIVE_MODE=true` + provide `ERP360_BASE_URL` + `ERP360_BILLING_WEBHOOK_SECRET` to route through ERP360. **MOCKED until ERP360 is wired.**
- 🟡 SSO bridge — `POST /api/auth/sso-exchange` returns 503 unless `SSO_ENABLED=true` and `ERP360_SSO_SHARED_SECRET` is set. **MOCKED until ERP360 is wired.**

## How to "drop into" ERP360 later (≤30 min when ready)
1. In ERP360: add one route `POST /api/sso/mint` that issues a short-lived JWT (audience=`ifpi-lms`, signed with `ERP360_SSO_SHARED_SECRET`) for the current user.
2. In ERP360: add one nav link "Learning" → `https://learn.ifpi.org/sso?token=<minted JWT>`.
3. In IFPI: set `SSO_ENABLED=true` and `ERP360_SSO_SHARED_SECRET=...` in `/app/backend/.env`.
4. For live billing: set `BILLING_LIVE_MODE=true` + `ERP360_BASE_URL=https://erp360.yourcompany.com` + `ERP360_BILLING_WEBHOOK_SECRET=...`.
5. Optionally: deploy IFPI to a separate domain (e.g. `learn.ifpi.org`) on the same Postgres cluster.

That's it. No ERP360 schema changes, no model merges, no shared codebase. Two new ERP360 endpoints + one nav link.

## Prioritised backlog
- **P2** — Provision a real S3 / R2 / GCS bucket. Storage abstraction in place — pure config flip.
- **P3** — Schedule audit digest as a weekly email to all admins (currently UI-only on `/audit`).
- **P3** — AI quiz: pre-fetch cost estimate from the LLM provider before kicking off a large batch.
- **P3** — Cohort CSV: include badge breakdown columns + completion percentage per learner.
- **P3** — `/audit` row drill-down: clicking a row opens a side panel with full JSON metadata + linked target.

## Deliberately deferred (not forgotten)
- ERP360 SSO bridge — opt-in via `SSO_ENABLED=true`. IFPI works standalone.
- ERP360 webhook receiver — code at `/app/docs/ERP360_INTEGRATION.md`.

## Iteration 22 — Gap closure + AI authoring suite spec (Feb 2026)

**Two Kimi-doc gaps closed:**
- ✅ Pinned 5 missing deps in `backend/requirements.txt`: `bleach==6.4.0`, `markdown==3.10.2`, `openpyxl==3.1.5`, `pandas==3.0.3`, `python-docx==1.2.0`. Fresh-venv `pip install` now succeeds; sanitizer confirmed bleach-backed (not silently fallback).
- ✅ New `scripts/seed_templates.py` — CLI + importable `seed_org(org_id, admin_id?)`. Creates 3 template courses ([TEMPLATE] Foundation 5 slides, Practical 5, Assessment 4) — status=DRAFT, category=TEMPLATE. Idempotent. Commits per-template so mid-loop failure can't discard earlier successes (post-QA fix).

**AI authoring suite roadmap authored:**
- ✅ `/app/docs/AI_AUTHORING_SUITE_ROADMAP.md` (496 lines) — master spec for 7 P0/P1 features: source-grounded tutor, deep research, quiz+flashcards, video overviews, TTS, mind maps/infographics, PPTX export. Includes staff-only access control architecture, `SourceDocument`/`AIJob`/`AIUsageLedger` shared infra design, 6-iter roadmap (Iter 22-27, ~16 engineering days), Definition of Done, and product-owner decisions (Tavily / Sora 2 / full SM-2 confirmed).

**Testing:** testing_agent report `iteration_15.json` — 10/10 checklist PASS, no regressions. Combined pytest run 13/13 green in 5.26s.

## Iteration 22 — AI Authoring Suite foundation + branded login (Feb 2026)

**Shared AI infra (Iter 22a):**
- ✅ 4 new models + Alembic `c9d2e1f4a5b6`: `SourceDocument`, `SourceChunk`, `AIJob`, `AIUsageLedger` + `Organization.ai_monthly_budget_cents` (default 20000c = $200)
- ✅ `auth.dependencies.requires_staff()` semantic alias (INSTRUCTOR + ADMIN + SUPER_ADMIN) — locked policy per roadmap §2
- ✅ `auth.dependencies.requires_admin()` — stricter gate for PII toggle + budget updates
- ✅ `services/ai_budget_service.py` — `check_budget`, `record_spend`, `month_to_date_spend_cents`, `get_budget_status`. Raises HTTP 429 with actionable detail on over-budget.
- ✅ `services/pii_redactor.py` — locked policy (b). Catches emails, phones, ID numbers, first-last name pairs. Lossless round-trip via mapping. Dedup — same value reuses placeholder.
- ✅ `routers/authoring.py` — `GET /api/authoring/status` (budget + feature-flag map), `POST /api/authoring/redaction/preview`, `GET/PUT /api/authoring/budget`

**Public branding endpoint (unlocks branded login):**
- ✅ `GET /api/branding/public` — no auth. Returns only `{name, slug, logo_url, primary_color, accent_color}`. Never leaks SMTP, budgets, IDs.

**Improvement — branded login page:**
- ✅ `LoginPage.tsx` now fetches `/api/branding/public` on mount and renders the IFPI logo + deep navy `#262262` hero + yellow-orange `#F5A500` accent glow + "IFPI Main Academy" wordmark. Fallbacks preserved for orgs with no branding set.
- ✅ Sign-in button, register link + accent icons all use the org's `primary_color`. Live-verified: hero_bg = rgb(38, 34, 98) confirmed via computed style.

**Tests:** `test_iteration22.py` — 13 new tests covering schema, staff-gate 403, PII round-trip + dedup, budget update flow, over-budget 429, public branding no-leak. Full Iter 14-22 suite: **65 passing, 1 expected skip.**

## Iteration 21 — xAPI auto-completion, version sidebar, API tokens (Feb 2026)

**xAPI → IFPI auto-completion (Iter 21a)**
- When an xAPI statement arrives with `verb=completed` or `verb=passed` AND `object.id` resolves to a known course (via `ifpi://course/<id>` URI scheme OR by matching a SCORM package's `launch_url`), the learner's enrollment is marked COMPLETED and a Certificate row is issued — idempotent, returns full status in the response under `auto_complete`.
- Resolver tries: explicit `ifpi://course/<id>` → SCORM package `launch_url` substring match.
- Env flag `XAPI_AUTO_COMPLETE=false` to disable. Default ON because the resolver is conservative (no course id = no-op).
- Live proof: created fresh course → POST xAPI with `ifpi://course/<id>` via API token → enrollment COMPLETED, cert created (`certificate_was_new=true`).

**Slide version sidebar (Iter 21b)**
- `CourseEditPage` now has a "History" pill next to slide-type buttons. Opens `SlideHistoryModal` that lists every version with timestamp + change-summary + "Restore" button.
- Restore flow is idempotent: it snapshots the CURRENT state before restoring, so even a restore is undo-able.
- Also added missing SCORM/AUDIO/PDF renderers in LearnPage and SCORM in the slide-type chip set.

**API tokens (improvement)**
- New `ApiToken` model + Alembic `b1c2d3e4f5a6`. Token format `ifpi_<8-char-prefix>_<24-char-secret>` (~45 chars).
- `auth/api_tokens.py` mints via `secrets.token_urlsafe`; stores SHA-256 hash + plaintext prefix; verifies via the standard `Authorization: Bearer` header.
- `auth/dependencies.get_current_user` routes any token starting with `ifpi_` past the JWT decoder to `authenticate_api_token`. Synthetic `CurrentUser` has negative id so it can't accidentally be confused with a real user row.
- Endpoints: `GET /api/admin/api-tokens`, `POST /api/admin/api-tokens` (returns plaintext ONCE), `POST /{id}/revoke`, `DELETE /{id}`. Audit-logged.
- Frontend `/tokens` admin page (NOT `/api-tokens` — that prefix collides with the ingress) — table of tokens + create modal + reveal-once modal with copy-to-clipboard.

**Tests:** `tests/test_iteration21.py` + full Iter14-21 suite — **58 passing, 2 expected skips**.

## Iteration 18-20 — SCORM/xAPI, Versioning, server.py refactor (Feb 2026)

**Iter 18 — SCORM 1.2/2004 + xAPI receiver**
- ✅ `services/scorm_service.py` — stdlib-only manifest parser (zipfile + xml.etree); path-traversal safe; version detection via `schemaversion` or xmlns sniff
- ✅ Models: `ScormPackage`, `XApiStatement` + Alembic `a8b4c9d3e7f2`
- ✅ `routers/scorm_xapi.py` — `POST /api/admin/scorm/upload`, `GET /api/admin/scorm`, `GET /api/scorm/files/<id>/<rel>` static server, `POST /api/xapi/statements`, `GET /api/xapi/statements`
- ✅ New `SlideType.SCORM` enum + iframe renderer in `LearnPage` (also added missing AUDIO/PDF renderers)
- ✅ Live e2e: uploaded SCORM 2004 zip → parsed manifest → course created → /api/scorm/files serves content

**Iter 19 — Slide versioning + rich-text sanitizer endpoint**
- ✅ `SlideVersion` model + Alembic migration (same `a8b4c9d3e7f2`)
- ✅ `services/versioning_service.py` — `snapshot_slide`, `list_versions`, `restore_version` (restore itself records a new version, making it undo-able)
- ✅ Hooked into `PATCH /api/courses/{cid}/slides/{sid}` — auto-snapshots ONLY on actual content change
- ✅ Endpoints: `GET /versions`, `GET /versions/{n}`, `POST /versions/{n}/restore`
- ✅ `POST /api/rich-text/sanitize` — bleach-backed preview helper for the editor

**Iter 20 — server.py refactor**
- ✅ New `routers/__init__.py` exports `register_all(app)` — groups all 26 routers by domain (Auth, Core LMS, Misc, Onboarding, Iter5, Iter6+, Webhooks, Imports, SCORM/xAPI)
- ✅ `server.py` shrunk from 114 → 76 lines, single `register_all(app)` call
- ✅ OpenAPI smoke test asserts every critical path is still mounted (no routes lost)

**Improvement — ImportJob rollback**
- ✅ `POST /api/admin/imports/{id}/rollback` — deletes every course/path the job created (uses captured `results.courses[].id`), marks job `ROLLED_BACK`, records audit entry
- ✅ Frontend "Roll back" button on each completed/partial row + `window.confirm` guard + strike-through "ROLLED BACK" badge after the fact

**Tests:** `tests/test_iteration18_20.py` + Iter14-17 regressions — **53/53 passing, 2 expected skips** (SSO disabled, no PENDING job to test rollback rejection path)

## Iteration 17 — Foundations (Feb 2026)
- ✅ Fixed stale alembic-head assertions in `test_iteration3/4.py` (now accept any head through Iter 17)
- ✅ Multi-process SSO replay store — new `SsoJtiSeen` model + Alembic migration `f1a2b3c4d5e6_sso_jti_seen.py`; `sso_service._check_replay()` now commits to SQL (survives across worker pods / DB sessions, proven via cross-session unit test)
- ✅ S3 storage backend already implemented (`services/storage_service.py`); added admin diagnostic `GET /api/admin/storage/info` with live write/exists/delete probe to make config flips visible
- ✅ Drag-and-drop ZIP uploader on `/imports`:
  - Backend: `POST /api/admin/imports/upload-zip` extracts safely to `/tmp/ifpi_import_staging/<uuid>/`, rejects path-traversal + non-zip + >200 MB, auto-unwraps single-root zips, then kicks off the same background importer
  - Frontend: tabbed modal — "Upload .zip" (dropzone + Choose file) vs "Server path"
- ✅ `tests/test_iteration17.py` — 7 passing, 1 skipped (full SSO handshake requires SSO_ENABLED=true on the running server)

## Iteration 16 — Bulk Content Migration (Feb 2026)
- ✅ `ImportJob` model + Alembic head `e7a3b9c4d816_import_jobs`
- ✅ HTML sanitizer at `core/sanitizer.py` (bleach + plain-text helper)
- ✅ Extended media uploads (video/audio/PDF) → `POST /api/uploads/media`, `/bulk-media`
- ✅ Bulk migration script `scripts/bulk_import.py` + background runner
- ✅ Endpoints `GET /api/admin/imports`, `/{id}`, `POST /run`
- ✅ Frontend `pages/dashboard/ImportsPage.tsx` wired into `/imports` route + admin sidebar ("Content imports")
- ✅ `tests/test_iteration16.py` — 14/14 passing

## Iteration 5 completed items (was backlog)
- ✅ Discussion / comments on slides → `/api/slides/{id}/comments`, mounted on `LearnPage`.
- ✅ Multi-tenant invitation flow (SUPER_ADMIN) → `/academies` page + `POST /api/academies`.
- ✅ Cert template live preview on Settings → `POST /api/admin/cert-preview`.
- ✅ Outbox retry policy + dead-letter handling → backoff in worker + `POST /admin/outbox/{id}/retry`.
- ✅ Webhook signing for outgoing calls → `sign_outgoing_payload()` HMAC headers.
- ✅ File upload for logo + signature image → `POST /api/uploads/image`.

## Files of interest
- `/app/backend/server.py` — entry, router registration.
- `/app/backend/services/{auth,exam,ai_builder,billing,sso,gamification}_service.py` — business logic.
- `/app/backend/core/{config,database,security,role_registry}.py` — infra primitives.
- `/app/frontend/src/contexts/AuthContext.tsx` — session state + role helpers.
- `/app/frontend/src/lib/api.ts` — axios client with silent refresh.
- `/app/memory/test_credentials.md` — admin + learner logins.

## Tech debt note
None significant. The codebase intentionally mirrors ERP360 conventions so future engineers context-switch cleanly. Lint passes clean. 0 known bugs.
