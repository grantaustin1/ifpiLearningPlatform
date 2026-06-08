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
- **P2** — Provision a real S3 / R2 / GCS bucket. Storage abstraction is already in place — just set `STORAGE_BACKEND=s3` + `S3_BUCKET=...` + AWS creds. Zero code change needed. *(Note: ERP360 also still runs on local disk — when they migrate, both apps flip together.)*
- **P3** — Outgoing /leads → ERP360 webhook receiver in ERP360 to verify the HMAC headers we now emit.
- **P3** — Drag-reorder for badge tiers + course catalog ordering.
- **P3** — Sort/filter/search on the Academies page once there are many tenants.

## Deliberately deferred (not forgotten)
- ERP360 SSO bridge (`POST /api/sso/mint` on ERP360 + flip `SSO_ENABLED=true` here). IFPI is fully functional without it — every ERP360 integration seam (SSO, live billing, mail dispatch) is feature-flagged off by default. Activating any of them is a single env-var change.

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
