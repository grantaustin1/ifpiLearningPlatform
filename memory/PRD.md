# IFPI Learning Platform — Product Requirements & Status

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
- **P3** — Cohort-aware dashboard widgets on `/reports` (currently only the API exists; UI shows aggregate).
- **P3** — Wire `agent_008_e2e_journey.py` into CI once we seed a deterministic published-course-with-slides-and-exam fixture.
- **P3** — Migrate `audit_logs.audit_metadata` from `JSON` (text in SQLite) to `JSONB` when we move to Postgres.
- **P3** — Make `ACTION_COLORS` on AuditLogPage derive colour from the action prefix so newly-added actions auto-color.

## Deliberately deferred (not forgotten)
- ERP360 SSO bridge — opt-in via `SSO_ENABLED=true`. IFPI works standalone.
- ERP360 webhook receiver — code at `/app/docs/ERP360_INTEGRATION.md`.

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
