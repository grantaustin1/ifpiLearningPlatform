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
- **P1** — Cert PDF: add IFPI logo to the template (currently uses a wordmark — replace with actual SVG/PNG when supplied).
- **P1** — Course prerequisites enforcement: schema exists (`course_prerequisites` table) but the LearnPage doesn't yet block entry if prereqs incomplete. Add a check in `POST /api/courses/{id}/enroll`.
- **P2** — Discussion / comments on slides.
- **P2** — Instructor invitation flow (today admin upgrade is DB-only).
- **P2** — Course duplication / templates.
- **P3** — Frontend: drag-reorder slides + path items in the editors.
- **P3** — Cert PDF template variants (badge/CPD/exam-pass) and per-academy branding.
- **P3** — Background job to email new certificates as PDF attachments (would reuse ERP360 mail transport once wired).

## Files of interest
- `/app/backend/server.py` — entry, router registration.
- `/app/backend/services/{auth,exam,ai_builder,billing,sso,gamification}_service.py` — business logic.
- `/app/backend/core/{config,database,security,role_registry}.py` — infra primitives.
- `/app/frontend/src/contexts/AuthContext.tsx` — session state + role helpers.
- `/app/frontend/src/lib/api.ts` — axios client with silent refresh.
- `/app/memory/test_credentials.md` — admin + learner logins.

## Tech debt note
None significant. The codebase intentionally mirrors ERP360 conventions so future engineers context-switch cleanly. Lint passes clean. 0 known bugs.
