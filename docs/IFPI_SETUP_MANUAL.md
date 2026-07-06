# IFPI Learning Academy — Setup Manual v1.0

> **"The Idiots Guide" for administrators bringing up a new IFPI tenant.**  
> Structured as a 6-phase forensic walkthrough — every step lists **what to do, what breaks if you skip it, and how to verify.**

**Audience:** Organization Owners, Super Admins, Instructor-Leads doing first-time setup.  
**Prerequisite:** You have Owner credentials from IFPI Platform Ops.  
**Time budget:** 45–90 minutes to complete Phases A–F (excluding content authoring).

---

## Table of Contents

0. [Pre-Flight — First Login & System Orientation](#0-preflight)
1. [Phase A — Branding & Academy Identity](#phase-a)
2. [Phase B — Personnel, Cohorts & the Role Fortress](#phase-b)
3. [Phase C — Courses, Learning Paths & Prerequisites](#phase-c)
4. [Phase D — AI Authoring Suite Configuration](#phase-d)
5. [Phase E — Integrations (ERP360 SSO, Webhooks, API Tokens, SCORM)](#phase-e)
6. [Phase F — Compliance, Certificates & Public Catalog](#phase-f)
7. [Phase G — Production Deployment & Observability](#phase-g)
8. [Audit & Verification Checklist](#audit)
9. [Failure Scenario Matrix](#failures)

---

# 0. Pre-Flight — First Login & System Orientation {#0-preflight}

## Step 0.1 — Initial Login

| Field | Value |
|---|---|
| **URL** | `https://<your-tenant>.ifpi.example.com/login` |
| **Route** | `/login` → `POST /api/auth/login` |
| **First user** | Provisioned automatically as `admin@<org>.ifpi.org` |
| **Password** | Set at tenant creation by Platform Ops |

### What you see on first login
- **Dashboard** with 4 KPI tiles (Active Learners, Courses Published, Certificates Issued, AI Spend This Month)
- **Health chip** in header — green when API + DB + storage are all live
- **"Onboarding wizard"** modal if this is the first Owner session (Phases A–F guided)

### What if this fails?
- **`401 INVALID_CREDENTIALS`** → confirm you're on the right tenant subdomain
- **`503`** → backend is warming up. Retry after 30 s
- **Blank page** → hard-refresh; the SPA uses localStorage for the JWT

### Zero-blocker check
Change the Owner password immediately (`Profile → Security → Change Password`). The default password is shared with Platform Ops.

### Iter 32 — Forced password change on first login
Every seeded admin account is created with `must_change_password=true`. On first login the app **auto-redirects** to `/change-password?forced=1`. You cannot reach the dashboard until the password is rotated. This eliminates the "shared default password" attack surface.

- Endpoint: `POST /api/auth/change-password` (JWT-gated, requires the current password)
- Frontend page: `frontend/src/pages/auth/ChangePasswordPage.tsx`
- Rescue CLI (locked-out admin): `python /app/backend/scripts/reset_admin_password.py --email admin@ifpi.org` — will set a new random password and mark `must_change_password=true` again so the human still has to rotate on next login.

### Iter 33 — Email verification enforcement
New self-registrations receive a verification email. Until they click the link, `user.email_verified_at` is `NULL` and access to sensitive routes is denied (403 `EMAIL_NOT_VERIFIED`). Re-issue via `POST /api/auth/resend-verification` (rate-limited to 2/hour per user).

- Verify endpoint: `POST /api/auth/verify-email` — consumes the single-use token.
- Frontend pages: `VerifyEmailPage.tsx`, `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`.

### Iter 33 — Forgot password / reset flow
`Profile → Sign in → Forgot password?` sends a single-use link (24 h TTL) via SMTP. Rate limit: 3/hr per email + 10/hr per IP. Tokens are hashed at rest in the `password_reset_tokens` table.

- `POST /api/auth/forgot-password` `{email}` → always returns 200 (does not leak existence).
- `POST /api/auth/reset-password` `{token, new_password}` → 200 on success, invalidates the token.

---

# Phase A — Branding & Academy Identity {#phase-a}

**Route:** `/dashboard/organization/settings`  
**Permission:** `OWNER`, `SUPER_ADMIN`

## Step A.1 — Organization Profile

| Field | Impact |
|---|---|
| **Name** | Appears on certificates, invitation emails, PDF exports |
| **Slug** | Used in `POST /api/public/catalog?slug=` and email links; **cannot be changed after certificates are issued** |
| **Timezone** | All streaks, deadlines, cohort digests fire in this TZ; **do not change once learners exist** |
| **Locale** | Default UI language for new learners; overridable per user |

### Impact analysis
Timezone changes mid-operation shift **all historical enrollment timestamps** on displays (streaks re-compute from raw UTC). Set this correctly on day 0.

### Verify
- `GET /api/organizations/current` returns the profile
- Certificate previews (Phase F) render with the new name

## Step A.2 — Branding (Colors + Logo)

- **Primary color** cascades to: sidebar accent, button primaries, certificate ribbon, PDF headings, email HTML links.
- **Logo** appears on: `/login`, sidebar header, cert PDF top-left, transcript PDF.

### What if this fails?
- Upload rejected (>2 MB or wrong MIME) → toast with size limit. IFPI accepts `png`, `jpg`, `svg`.
- Logo doesn't appear on cert → clear the cert cache by regenerating one preview.

## Step A.3 — Certificate Template

Pick one of the built-in templates or upload a custom Nano-Banana-generated banner (`Authoring → Visuals → Generate certificate banner`).

- Preview via `GET /api/certificates/preview?course_id=<any>`
- Verify link + QR are auto-added in the bottom-right (Iter 30b)

---

# Phase B — Personnel, Cohorts & The Role Fortress {#phase-b}

**Route:** `/dashboard/users` and `/dashboard/academies`  
**Permission:** `ADMIN`+

## Step B.1 — Understanding IFPI's Role Matrix

<!-- AUTO:BEGIN role_matrix -->
| Role | Description |
|---|---|
| `SUPER_ADMIN` | Platform super-admin — can manage all academies |
| `ADMIN` | Academy administrator — full control of one academy |
| `INSTRUCTOR` | Can create courses/exams and grade learners |
| `BILLING_VIEWER` | Read-only access to billing/invoicing |
| `LEARNER` | End-user enrolled in courses (default) |
<!-- AUTO:END role_matrix -->

**Alias tolerated from external systems / SSO (auto-mapped):**

<!-- AUTO:BEGIN role_aliases -->
| Alias | Canonical |
|---|---|
| `OWNER` | `ADMIN` |
| `MANAGER` | `ADMIN` |
| `PLATFORM_ADMIN` | `SUPER_ADMIN` |
| `TRAINER` | `INSTRUCTOR` |
| `STUDENT` | `LEARNER` |
| `USER` | `LEARNER` |
<!-- AUTO:END role_aliases -->

Roles are **additive** — a user with `INSTRUCTOR` + `LEARNER` sees both dashboards.

## Step B.2 — Creating Users

Two paths:

1. **Invitation** (recommended for humans)
   - `Users → Invite` → email(s), role, cohort
   - `POST /api/admin/invitations/bulk` behind the scenes
   - Invitee clicks link, sets password → JIT-provisioned into your org

2. **SSO handshake** (recommended when ERP360 is enabled — see Phase E.1)
   - Users appear in IFPI **on first sign-in from ERP360** with roles mapped by policy (see [SSO role mapping](#sso-roles))

## Step B.3 — Cohorts

Cohorts group learners for:
- Leaderboards (`/dashboard/leaderboard?cohort=INTAKE-2026-Q1`)
- Bulk-invitations
- Digest emails (weekly cohort recap)
- Certificate-issuing rules

**Naming convention:** `<STREAM>-<YEAR>-<INTAKE>` (e.g., `SALES-2026-Q1`). Cohorts are ≤100 chars.

## Step B.4 — Two-Factor Authentication (RECOMMENDED)

**Status: SHIPPED in Iter 30i.** IFPI supports TOTP (Google Authenticator / 1Password / Authy) with recovery codes.

- Enable: `Profile → Security → Two-Factor Authentication → Set up`.
- Flow: `POST /api/auth/2fa/setup-init` → scan QR → confirm 6-digit code → `POST /api/auth/2fa/setup` returns 10 one-time recovery codes.
- Disable (self): `POST /api/auth/2fa/disable` (requires current password + a valid TOTP or recovery code).
- Admin override: `POST /api/admin/users/{id}/2fa/disable` — audit-logged.
- Login challenge: When 2FA is on, `/api/auth/login` returns `{challenge_id}` with `2FA_REQUIRED`; complete via `POST /api/auth/2fa/challenge`.

SSO users continue to inherit MFA from ERP360 (Phase E.1) instead.

---

# Phase C — Courses, Learning Paths & Prerequisites {#phase-c}

**Route:** `/dashboard/courses`  
**Permission:** `INSTRUCTOR`+

## Step C.1 — Create a Course

| Field | Impact |
|---|---|
| **Title** | Shown on catalog, cert PDF, transcript |
| **Category** | Filters the public catalog + admin lists |
| **Passing Score** | Applies to the summative exam only (default 70) |
| **Duration Estimate** | Displayed to learners; feeds workload heatmaps |
| **Price (cents)** | Set > 0 to enable Stripe checkout on the catalog (backlog) |
| **Status** | `DRAFT` → `PUBLISHED` → `ARCHIVED`. Only `PUBLISHED` shows on catalog |

## Step C.2 — Add Slides

Two options:
1. **Manual** — one at a time via the slide editor.
2. **AI generation** — `Authoring → Course Builder → Generate outline`. See Phase D.

Each slide has: `title, content (HTML/MD), slide_type (TEXT/VIDEO/QUIZ/…), media_url, narration_url, order_index`.

## Step C.3 — Prerequisites

`Course → Prerequisites → Add`. Prevents `POST /api/courses/{id}/enroll` for learners who haven't completed the prereq.

**Rule:** Prerequisites are **DAG-checked** — creating a cycle returns `422 CYCLE_DETECTED`.

## Step C.4 — Learning Paths

A learning path is an **ordered set of courses**. Best-fit for:
- Certification tracks (e.g., "IFPI Sales Foundation → Advanced → Master")
- Onboarding journeys (7 courses, sequential unlock)

Route: `/dashboard/learning-paths`

## Step C.5 — Publish

`Course → Status → PUBLISHED` runs a **pre-publish audit**:
- ≥ 1 slide with `is_required=true`
- Slide `order_index` values are contiguous
- Passing exam exists (if `passing_score > 0`)

Failing the audit returns `422 COURSE_NOT_PUBLISHABLE` with a checklist.

---

# Phase D — AI Authoring Suite Configuration {#phase-d}

**Route:** `/dashboard/authoring/*`  
**Prerequisite:** Emergent LLM Key is configured by Platform Ops (Universal Key).

## Step D.1 — Set the AI Spend Budget

`Organization Settings → AI Budget`  
- **Monthly USD cap** (default $50) — enforced by `services/ai_budget_service.py`
- **Per-course cap** (default $5) — prevents a runaway single course
- **Alert threshold** (default 80 %) — emails Owners when hit

Verify: `/dashboard/tokens` shows the 14-day spend chart with your budget line.

## Step D.2 — Choose Default Models per Feature

| Feature | Default | Alternates |
|---|---|---|
| Course/Slide generation | `gpt-4o` | `claude-4.5`, `gemini-3-pro` |
| Flashcards | `gpt-4o-mini` | `claude-4.5-haiku` |
| Narration (TTS) | `openai-tts-1` | multi-language auto-detect |
| Infographic | `nano-banana` | (image only) |
| Video overview | `sora-2` | (video only) |
| Deep research | `tavily` (API key required) | — |
| Tutor Q&A | `gpt-4o` | `claude-4.5` |

## Step D.3 — Optional API Keys

| Integration | Env Var | Where |
|---|---|---|
| Tavily (Deep Research) | `TAVILY_API_KEY` | Platform Ops or self-serve `Settings → Integrations` |
| Sora 2 / Nano Banana / TTS / GPT | Emergent LLM Key | already set by Platform Ops |

## Step D.4 — Enable Voices for Multi-Lang TTS

`Authoring → Narration` supports 8 base languages (`en, es, fr, de, hi, ja, pt, zh`). Pick a default per academy.

---

# Phase E — Integrations {#phase-e}

## Step E.1 — ERP360 SSO Handoff {#sso-roles}

**Purpose:** Let staff sign in to IFPI using their ERP360 identity, without a second password.

### Enable
1. In IFPI backend `.env`:
   ```env
   SSO_ENABLED=true
   ERP360_SSO_SHARED_SECRET=<shared HS256 secret from ERP360 Platform Admin>
   SSO_ISSUER=erp360
   SSO_AUDIENCE=ifpi-lms
   ```
2. Restart backend (`supervisorctl restart backend`).
3. Verify: `GET /api/auth/sso-status` returns `{"enabled": true}`.

### Handshake flow
1. In ERP360, user clicks the "Open Learning Academy" tile.
2. ERP360 mints an HS256 JWT with claims: `iss, aud, sub, email, name, roles, iat, exp (60 s), jti`.
3. Browser posts to `POST /api/auth/sso-exchange`.
4. IFPI validates signature + issuer + audience + jti (replay), JIT-provisions the user if new, and returns IFPI's own access token.

### Role mapping (default)
| ERP360 Role | IFPI Role |
|---|---|
| `OWNER`, `SUPER_ADMIN`, `ADMIN` | `ADMIN` |
| `MANAGER` | `ADMIN` |
| `TRAINER` | `INSTRUCTOR` |
| `VIEWER`, `RECEPTION`, `MEMBER` | `LEARNER` |
| unknown | `LEARNER` (fail-safe) |

### Testing
```bash
curl -X POST https://<ifpi>/api/auth/sso-exchange \
  -H "Content-Type: application/json" \
  -d '{"erp_token": "<signed_jwt>"}'
```

## Step E.2 — API Tokens

**Route:** `/dashboard/tokens`. Roles: `ADMIN`+

Create scoped tokens for machine access:

| Scope | Grants |
|---|---|
| `read:catalog` | Anonymous public catalog + verify endpoints |
| `read:analytics` | KPI + spend dashboards |
| `write:courses` | Course + slide CRUD |
| `write:learners` | Bulk invite + user CRUD |
| `sign:webhooks` | HMAC verifying inbound webhooks |

Tokens are **shown once at creation**. Every call is logged in `api_token_calls` for the usage analytics chart.

## Step E.3 — Outgoing Webhooks

**Route:** `/dashboard/webhooks`. Roles: `ADMIN`+

Subscribe to events: `course.published`, `enrollment.completed`, `certificate.issued`, `learner.invited`, `ai.spend.threshold`.

- **HMAC signed** with per-webhook secret in `X-IFPI-Signature`.
- **Retry:** exponential backoff for 24 h; dead letter shown in the UI.

## Step E.4 — SCORM / xAPI Publishing

Enable in `Course → Publish → SCORM`. IFPI serves a SCORM 1.2/2004 runtime shim at `/api/scorm/runtime.js` so external LMSes can import your courses as `.zip` packages.

## Step E.5 — Sibling-App Mode vs Stand-Alone

IFPI runs in **either mode** with no code changes:

| Mode | How to enable | Impact |
|---|---|---|
| **Stand-alone** | Default. `SSO_ENABLED=false` | Users log in with local password, invitations via email. |
| **Sibling to ERP360** | `SSO_ENABLED=true` + shared secret | ERP360 users appear via SSO; billing can be routed to ERP360 lite-billing (backlog toggle). |

See [`docs/IFPI_INTEGRATION_MATRIX.md`](../IFPI_INTEGRATION_MATRIX.md) for the sync boundary contract.

---

# Phase F — Compliance, Certificates & Public Catalog {#phase-f}

## Step F.1 — Certificate Verification

Every issued certificate carries:
- Unique 22-char alphanumeric `certificate_code`
- Signed `verifier_token` (JWT, cannot be forged)
- Public QR + click-through link on the PDF (Iter 30b)
- `GET /api/public/certificates/verify/{code}` returns holder + course + issued-at

Rate limit: 30/min per IP (Redis-backed, shared across replicas).

## Step F.2 — Public Catalog

`Organization Settings → Public Access → Enable`  
- Anonymous browsing at `/catalog?token=<read:catalog token>` (or an internal API token)
- Only `PUBLISHED` courses appear
- Verify pane at `/catalog?verify=<code>` for third parties (recruiters, regulators)

## Step F.3 — Retention & Deletion (GDPR / POPIA)

| Data class | Retention | Deletion path |
|---|---|---|
| Learner PII | 7 y after last activity | Owner-only `DELETE /api/users/{id}?hard=true` (audit-logged) |
| Certificate | Forever (verifiability) | Revoke via `POST /api/certificates/{id}/revoke`; PDF re-issue blocked. Bulk: `/api/certificates/bulk-revoke`, `/api/certificates/bulk-unrevoke` (Iter 30–31) |
| AI logs / prompts | 90 d | Auto-purged by `outbox_worker` |
| Audit log | 3 y | Not user-deletable |

### Iter 33 — Self-service GDPR endpoints
Learners no longer need to email support to exercise their data rights:

| Right | Endpoint | Notes |
|---|---|---|
| **Data portability** | `GET /api/auth/me/export` | Streams a ZIP with `profile.json`, `courses.json`, `certificates.json`, `flashcards.json`, `audit.json`. |
| **Erasure — request** | `POST /api/auth/me/delete-request` | Emails a 6-digit confirmation code (10 min TTL). |
| **Erasure — confirm** | `DELETE /api/auth/me` | Consumes the code, anonymises PII, revokes certificates, purges sessions. Certificate PDFs remain verifiable via the anonymised holder token. |

Frontend surface: `Profile → Privacy` (`PreferencesPage.tsx`).

### Iter 31 — Compliance auto-reports
Env-gated worker (`COMPLIANCE_REPORT_ENABLED=true`) that emails a monthly PDF summary to `COMPLIANCE_REPORT_RECIPIENTS`. Covers active users, certs issued/revoked, deletion requests, failed logins, and top audit events. See `IFPI_WEBHOOK_EVENTS.md` for the parallel event stream.

## Step F.4 — Streaks, Badges & Cohort Digests

Enable in `Organization Settings → Gamification`:
- **Streaks** — daily activity counter, resets at TZ-midnight
- **Badges** — earned per course + exam completion (see `badge_tiers` table)
- **Cohort digest** — weekly recap emailed to every learner in a cohort

---

# Phase G — Production Deployment & Observability {#phase-g}

**Status:** Iter 32 hardening. All items below are **required** before flipping the tenant to a public URL.

## Step G.1 — Pre-flight config validation

`python /app/backend/scripts/deploy_precheck.py` is a **fail-closed** script that boot-blocks the backend if any of these are wrong:

| Rule | What it checks |
|---|---|
| `ENVIRONMENT` set | Missing → assumed `production` (strictest mode). |
| No dev secrets in prod | Rejects `JWT_SECRET=changeme`, `SEED_ADMIN_PASSWORD=admin123`, etc. |
| `MONGO_URL` absent | IFPI is **PostgreSQL-only**. Any Mongo config aborts boot. |
| Storage backend | `STORAGE_BACKEND=s3` requires `S3_*` vars. `local` blocks prod boot. |
| CORS | Wildcard `*` rejected when `ENVIRONMENT=production`. |
| Sentry DSN | Warning if missing (not fatal). |

Wire this into your container `ENTRYPOINT` so bad configs never reach a healthy pod.

## Step G.2 — Environment template

`/app/.env.production.template` — copy to `.env.production` and fill:

- `DATABASE_URL` (Neon / RDS Postgres — must be `postgresql+psycopg2://…`)
- `JWT_SECRET` (32+ random bytes; rotate every 90 d)
- `SEED_ADMIN_PASSWORD` (governs the seeded owner in prod — never `admin123`)
- `STORAGE_BACKEND=s3` + `S3_*` (Cloudflare R2 or AWS S3)
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` (Resend / SES / Mailgun)
- `SENTRY_DSN` (both backend + frontend; separate DSNs recommended)
- `ALLOWED_ORIGINS=https://academy.<your-org>.com` (exact, no wildcards)
- `RATE_LIMIT_REDIS_URL` (optional but recommended for multi-replica)

## Step G.3 — Security headers

`core/middleware.py::SecurityHeadersMiddleware` adds on every response:

- `Content-Security-Policy` — locked to self + integrated third-parties (Sentry, Tavily)
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`
- `Permissions-Policy: camera=(), microphone=(self), geolocation=()`

Verify with `curl -I https://<your-host>/api/health | grep -i "content-security"`.

## Step G.4 — Sentry & correlation IDs

- `sentry_sdk` initialised in `server.py` with tracing sample-rate `0.2` and `environment` tag from `ENVIRONMENT`.
- Every request gets an `X-Correlation-ID` header (generated or forwarded). Logged via `CorrelationIdMiddleware` and attached to every Sentry event.
- Frontend forwards the same header via the Axios interceptor so front + back stack traces link automatically.

## Step G.5 — Rate limiting

- Redis-backed via `services/rate_limit_service.py`. Falls back to an in-memory bucket if `RATE_LIMIT_REDIS_URL` is unset (single-replica dev only).
- Endpoints covered: `/auth/login`, `/auth/forgot-password`, `/auth/register`, `/auth/verify-email/resend`, `/public/certificates/verify/{code}`, `/marketplace/*`.
- Client IP resolved from `X-Forwarded-For` (K8s ingress). Test override: `X-Test-Client-Ip` header, only when `ALLOW_TEST_TOKEN_HEADER=true`.

## Step G.6 — Locked-out admin rescue

If the owner rotates the seeded password wrong twice and gets locked out:

```bash
cd /app/backend
python scripts/reset_admin_password.py --email admin@ifpi.org
# Prints a random 20-char password, sets must_change_password=true.
# Hand this to the admin over a secure channel; they'll rotate on next login.
```

The seed script itself (`seed/seed_minimal.py`) is **idempotent** — it will NEVER overwrite an existing user's password. Proved by test `test_iteration33_sprint.py::test_seed_does_not_overwrite_existing_admin`.

## Step G.7 — pgvector activation (P2 option a, Iter 34)

The RAG tutor is **pgvector-ready** but ships in Python-cosine fallback mode. To activate the fast path in production:

1. **Provision** — Neon Postgres (or any Postgres 15+) with the `vector` extension enabled. Neon: `Settings → Extensions → vector`. Self-hosted: `sudo apt install postgresql-15-pgvector`.
2. **Flip flag** — set `USE_PGVECTOR=true` in `.env.production` (or your K8s config-map). Model-level column type + service query branch both read this at import / call time.
3. **Migrate** — `alembic upgrade head`. Migration `d2e3f4a5b6c7_pgvector_ready.py`:
   - Is a **NO-OP on SQLite** (dev)
   - Is a **NO-OP on Postgres without the `vector` extension available** (safe cluster)
   - When both conditions are met, runs `CREATE EXTENSION vector`, alters `source_chunks.embedding` from `json` to `vector(1536)` (cast in-place, no data loss), and creates an HNSW cosine index.
4. **Verify** — `SELECT indexname FROM pg_indexes WHERE tablename='source_chunks'` should show `ix_source_chunks_embedding_hnsw`. Any semantic-search request will now use `<=>` cosine distance in Postgres instead of the Python fallback.

**Rollback** — the same migration downgrade path casts the column back to `json`. Application code adapts automatically because `services/embedding_service.py::_use_pgvector()` short-circuits when the flag flips off.

**Capacity note** — pgvector's design ceiling on a modest Neon compute (1 vCPU, 4 GB) is ~1M chunks with sub-100ms search. Above that, tune the HNSW `m` / `ef_construction` params in the migration.

---

# Audit & Verification Checklist {#audit}

Run this before your first learner cohort goes live.

- [ ] Organization profile complete (name, TZ, locale)
- [ ] Logo + primary color set; cert preview looks right
- [ ] At least one `PUBLISHED` course with ≥ 5 slides + a passing exam
- [ ] One test learner enrolled → completes → cert issued → verify URL works
- [ ] `GET /api/health` returns `{status: "ok"}`
- [ ] `GET /api/public/certificates/verify/<test_code>` returns 200
- [ ] AI budget capped + alert email tested
- [ ] SSO-status endpoint reachable (if enabling ERP360 SSO)
- [ ] At least one webhook subscribed and delivered a `test.ping` event
- [ ] Backup / export: run `POST /api/admin/exports/full` and download the ZIP
- [ ] **Iter 32:** `python backend/scripts/deploy_precheck.py` exits 0
- [ ] **Iter 32:** `curl -I` shows `Strict-Transport-Security` + `Content-Security-Policy`
- [ ] **Iter 32:** Trigger a test Sentry event; confirm it appears in the project
- [ ] **Iter 33:** New user receives verification email; unverified access returns 403
- [ ] **Iter 33:** `GET /api/auth/me/export` returns a ZIP with 5 JSON files
- [ ] **Iter 33:** Rate-limiter blocks 6th failed login within 60 s (`429`)

---

# Failure Scenario Matrix {#failures}

| Symptom | Cause | Fix |
|---|---|---|
| Users can't log in | JWT_SECRET rotated without invalidation broadcast | Restart backend; users re-login |
| SSO returns 401 SSO_INVALID_TOKEN | Clock skew or wrong shared secret | Sync NTP + confirm `ERP360_SSO_SHARED_SECRET` matches |
| Course fails to publish | Slide `order_index` non-contiguous | Rebalance via `POST /api/courses/{id}/slides/reorder` |
| AI spend chart empty | Budget service hasn't recorded a call | Trigger any AI generation to seed data |
| Certificate verify returns 429 | Bot enumeration | Rate limit fired (Redis); wait 60 s or raise the limit in `services/rate_limit_service.py` |
| Webhook stuck FAILED | Endpoint 5xx > 3 attempts | Fix endpoint, click "Retry" in `/dashboard/webhooks` |
| SCORM package won't import | Missing `imsmanifest.xml` root | Re-export via `/dashboard/courses/{id}/export-scorm` |
| Backend refuses to boot in prod | `deploy_precheck.py` found a dev secret or missing config | Read the printed error, fix the env var, redeploy |
| Admin locked out after password rotation | Wrong password entered on forced-change screen | Run `python backend/scripts/reset_admin_password.py --email admin@…` |
| Users report "please verify your email" 403 | `email_verified_at` is NULL | Ask user to click link, or `POST /api/auth/resend-verification` |
| Forgot-password email never arrives | SMTP mis-configured OR rate limit hit (3/hr per email) | Check `Organization → SMTP → Send test`; check `outbox_messages` for FAILED rows |
| Sentry not receiving events | `SENTRY_DSN` missing OR sample-rate `0.0` | Confirm env var; trigger `/api/_test/raise` (dev only) |
| CSP blocks a legit third-party script | Domain not in the allow-list | Edit `SecurityHeadersMiddleware.CSP_POLICY` in `core/middleware.py` |

---

*Auto-generated from IFPI v1.0 route registry. Do not hand-edit — regenerate with `python /app/backend/scripts/build_setup_guide.py`.*
