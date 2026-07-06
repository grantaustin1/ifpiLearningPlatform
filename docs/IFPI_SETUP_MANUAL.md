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

# 0. Getting In — First Login & What You'll See {#0-preflight}

> **In plain English:** How to log in for the first time, what the app looks like when you land, and what to do if something goes wrong.

## 0.1 — Your first sign-in

- **Where:** `https://<your-tenant>.ifpi.example.com/login`
- **Who set up your login:** IFPI Platform Ops. They will have emailed you an email address and a temporary password.
- **What happens on first login:** IFPI will **force you to change the password** before it lets you into the dashboard. This is on purpose — the temporary password should never survive past day one.

Type your temporary password in the "current password" box, pick a new one (at least 8 characters, different from the old one), confirm it, and hit **Save**. You'll land on the dashboard.

## 0.2 — What the dashboard shows you

When you land you'll see:

- **Four key numbers at the top** — Active Learners, Courses Published, Certificates Issued, AI Spend This Month.
- **A little green health dot** in the header — this means the system is healthy. If it's ever red, take a screenshot and ping Platform Ops.
- **An onboarding checklist** if this is your first time — walks you through Phases A to F below.

## 0.3 — When something goes wrong

- **"Invalid credentials"** — double-check you're on the right website (the tenant address IFPI Ops gave you), and that you're typing the password with the right capitalisation. Copy-paste is safer than typing.
- **A blank white page** — hard-refresh the browser (Ctrl+Shift+R on Windows, Cmd+Shift+R on Mac).
- **"Server is warming up"** — wait 30 seconds and try again. This only happens on the first login of the day if the system was idle.

## 0.4 — Forgotten your password?

Click **"Forgot password?"** on the login screen. IFPI emails you a single-use reset link (valid for 24 hours). Follow it, pick a new password, done.

If you can't get in even with reset (e.g. the email address on file is wrong), contact IFPI Platform Ops. There's a rescue tool they can run to reset your account from the server side.

## 0.5 — Verifying your email address

New self-registered users get a verification email. Until you click the link, you can log in but you can't do sensitive things like publishing courses to the public catalogue. If the email didn't arrive, look under `Profile → Security → Resend verification`.

<details>
<summary><em>Technical reference for Platform Ops</em></summary>

- Login endpoint: `POST /api/auth/login`. Cookie-based auth; `access_token` is null in the response body by design (see `AUTH_COOKIE_MODE=on`).
- Forced-change flag: `user.must_change_password=true` — redirects to `/change-password?forced=1`.
- Change-password endpoint: `POST /api/auth/change-password` (requires current password + CSRF header).
- Forgot/reset: `POST /api/auth/forgot-password` (rate-limited 3/hr per email + 10/hr per IP), `POST /api/auth/reset-password`.
- Verify email: `POST /api/auth/verify-email` (single-use token, 24 h TTL).
- Rescue CLI: `python /app/backend/scripts/reset_admin_password.py --email <admin>` (requires `ADMIN_RESCUE_SECRET` env var).

</details>

---

# Phase A — Making It Look Like Your Academy {#phase-a}

> **In plain English:** Name your academy, upload your logo, pick your colour, and choose what your certificates should look like. Do this before you invite anyone — it's what learners will see first.

**Where:** `Organisation Settings` (under your name in the top-right).
**Who can do this:** the Owner and Super Admins.

## A.1 — Naming and identity

- **Academy name** — appears on every certificate, every email you send from IFPI, and every PDF export. Get this right.
- **Slug** — a short, URL-friendly version of your name (e.g. `ifpi-main`). This appears in shareable links. ⚠️ **Once you've issued certificates, you can't change this** — those links would break.
- **Timezone** — the clock IFPI uses when counting streaks, sending weekly digests, and stamping deadlines. Pick your headquarters timezone. ⚠️ **Don't change this after learners start using the system** — historical dates will visibly shift on screen.
- **Language** — the default UI language for new learners. Individual users can still switch to their own preferred language.

## A.2 — Colours and logo

- **Primary colour** — cascades everywhere: sidebar accent, buttons, certificate ribbon, PDF headings, email links. Pick a colour that reflects your brand.
- **Logo** — appears on the login screen, the sidebar header, the top-left of every certificate, and every transcript PDF. Upload a PNG, JPG, or SVG, max 2 MB.

If the upload gets rejected, it's almost always the file being too big or the wrong file type. Resize and try again.

## A.3 — Certificate design

You get two options:
- **Pick a built-in template** — pre-designed, works for most academies.
- **AI-generate a custom banner** — use IFPI's AI Authoring tool (`Authoring → Visuals → Generate certificate banner`) to make something unique to your brand. Great for corporate academies with a specific look.

Preview any certificate before you go live: click any course → **Preview Certificate** and see how it renders with real learner data.

<details>
<summary><em>Technical reference for Platform Ops</em></summary>

- Profile: `GET/PATCH /api/organizations/current`.
- Cert branding fields on `organizations` table: `cert_accent_color`, `cert_signature_text`, `cert_signature_image_url`, `cert_footer_text`, `theme_preset`.
- Preview URL: `GET /api/certificates/preview?course_id=<any>`.
- Verify link + QR are auto-added in the bottom-right of every PDF (Iter 30b).

</details>

---

# Phase B — Inviting People & Setting Their Access {#phase-b}

> **In plain English:** Add your team and learners, group them into cohorts (like classes), and decide what each person can do.

**Where:** `Users` in the sidebar.
**Who can do this:** Admins and above.

## B.1 — The five roles, in plain English

There are five levels of access. Everyone gets exactly one primary role, though someone can hold multiple if their job needs it (e.g. an instructor who's also enrolled as a learner).

- **Super Admin** — reserved for Platform Ops. Can manage every academy on the platform. You probably won't create these.
- **Admin** — full control of *your* academy. Can invite people, create courses, publish, manage billing, revoke certificates. This is what your senior staff should have.
- **Instructor** — can build courses, write exams, and grade learner submissions. Can't invite people or change billing.
- **Billing Viewer** — read-only look at invoices and spend. Give this to your finance person if they don't need to build content.
- **Learner** — the default. Enrols in courses, watches slides, sits exams, earns certificates. Cannot see the admin dashboard at all.

**If someone signs into IFPI from an external system** (like ERP360), IFPI translates the external role into one of these five automatically — no work needed from you.

## B.2 — Two ways to add people

**Option 1 — Invite by email (the normal way for humans).**
Go to `Users → Invite`, paste one or many email addresses, pick a role, optionally assign them to a cohort. IFPI sends each person an email with a signup link. They click, choose their password, and they're in.

**Option 2 — Single sign-on from ERP360 (if you use ERP360).**
Users don't need an IFPI invitation at all — the first time they click "Open Learning Academy" from ERP360, IFPI creates their account automatically with the right role. See Phase E for how to enable this.

## B.3 — Cohorts (groups of learners)

A cohort is just a group name you attach to learners. It lets you:
- **See a leaderboard just for that group** — great for competitive cohorts.
- **Invite a whole group at once** — paste 30 emails, all get the same cohort label.
- **Send weekly digest emails** to that group only.
- **Restrict certificate issuing** to only members of a specific cohort (e.g. "only issue this cert to the Sales 2026 Q1 cohort").

Suggested naming pattern: `STREAM-YEAR-INTAKE`, for example `SALES-2026-Q1` or `ONBOARDING-2026-NEW-HIRES`. Keep it under 100 characters.

## B.4 — Two-factor authentication (highly recommended for admins)

Any user can add **two-factor authentication** to their account for extra security. It works with Google Authenticator, 1Password, Authy, or any TOTP app.

**To turn it on for yourself:** `Profile → Security → Two-Factor Authentication → Set up`. Scan the QR code with your phone, enter the 6-digit code to confirm, and IFPI gives you **10 recovery codes**. Save these somewhere safe (a password manager) — they're what you use if you ever lose your phone.

**As an admin, you can also force a user to reset their 2FA** (e.g. they lost their phone) from `Users → [name] → Reset 2FA`. All 2FA resets are logged.

If your users sign in via ERP360 SSO, IFPI relies on ERP360's own MFA instead of asking for a second factor twice.

<details>
<summary><em>Technical reference for Platform Ops</em></summary>

- Role table: SUPER_ADMIN, ADMIN, INSTRUCTOR, BILLING_VIEWER, LEARNER.
- SSO alias mapping (see `role_registry.py`): OWNER/MANAGER→ADMIN, PLATFORM_ADMIN→SUPER_ADMIN, TRAINER→INSTRUCTOR, STUDENT/USER/VIEWER→LEARNER.
- Invitation endpoint: `POST /api/admin/invitations/bulk`.
- 2FA endpoints: `POST /api/auth/2fa/setup-init`, `POST /api/auth/2fa/setup`, `POST /api/auth/2fa/challenge`, `POST /api/auth/2fa/disable`.
- Admin 2FA reset: `POST /api/admin/users/{id}/2fa/disable` — audit-logged.
- Roles are additive; `user.user_roles` is a many-to-many list.

</details>

---

# Phase C — Building Courses & Learning Paths {#phase-c}

> **In plain English:** How to create a course, add slides to it, chain courses together into a learning path, and finally publish so learners can see it.

**Where:** `Courses` in the sidebar.
**Who can do this:** Instructors and Admins.

## C.1 — Create a course

Click **New Course** and fill in:
- **Title** — this is what learners will see. Also appears on the certificate.
- **Category** — helps learners filter the catalogue (e.g. "Sales", "Compliance", "Product").
- **Passing score** — the mark a learner needs on the exam. Default 70%.
- **Duration estimate** — how long you think the course takes. Shown to learners, feeds workload reports.
- **Price** — leave at 0 for a free course, or set an amount to charge learners (via Stripe — see Phase E).
- **Status** — starts at *Draft*. You'll flip this to *Published* once the course is ready.

## C.2 — Add slides

A slide is one piece of content. You can build a slide two ways:

- **Manually** — click *Add Slide*, choose the type (Text, Video, Audio, Image, PDF, or SCORM package), write the content, save.
- **With AI** — click *Generate outline* under Authoring → Course Builder. IFPI's AI reads any reference material you upload, drafts a full outline, and creates all the slides for you. You then edit anything you don't like. See Phase D.

Slides have an **order number**. Drag them around to reorder — the numbers update automatically.

## C.3 — Prerequisites (who can enrol)

You can require a learner to complete Course A before they can enrol in Course B. Go to `Course → Prerequisites → Add`.

If you accidentally create a loop (A requires B, B requires A), IFPI blocks the change and shows you the loop.

## C.4 — Learning paths (courses in a series)

A **learning path** is an ordered series of courses. Perfect for:
- Certification tracks — "IFPI Sales Foundation → Advanced → Master".
- Onboarding — 7 courses that unlock one after the other for new hires.

Go to `Learning Paths → New Path`, add courses in the order you want, and publish it. Learners see the whole journey and their progress through it.

## C.5 — Publishing

When you're ready to make a course visible to learners, flip its status from Draft to Published. IFPI does a pre-flight check first — it will refuse to publish if:
- The course has zero required slides.
- The slide order has gaps (this only happens if a slide was deleted incorrectly — rare).
- You set a passing score but forgot to add a passing exam.

If it refuses, it tells you exactly what's missing so you can fix it and try again.

<details>
<summary><em>Technical reference for Platform Ops</em></summary>

- Course model: `models/learning.py::Course`. Status enum: DRAFT | PUBLISHED | ARCHIVED.
- Publish endpoint: `PATCH /api/courses/{id}` with `{status: "PUBLISHED"}`. Returns `422 COURSE_NOT_PUBLISHABLE` with a checklist on failure.
- Prerequisite DAG check: creating a cycle returns `422 CYCLE_DETECTED` (`services/course_service.py`).
- Slide reorder: `POST /api/courses/{id}/slides/reorder`.
- Learning path model: `models/learning.py::LearningPath` + `LearningPathItem`.

</details>

---


# Phase D — Turning on AI Content Generation {#phase-d}

> **In plain English:** IFPI's AI can draft courses, generate quizzes, make flashcards, narrate slides, and even create images and videos. This phase is where you tell it how much to spend and which AI to use for each job.

**Where:** `Organisation Settings → AI Authoring`.
**Prerequisite:** Platform Ops has already given your tenant an "Emergent LLM Key" — you don't need to do anything with API keys yourself.

## D.1 — Setting a spending cap

Your team uses IFPI's AI features by clicking buttons. Each button click costs a small amount (typically a few cents). You control the monthly ceiling so nobody accidentally runs up a big bill.

- **Monthly cap** — default is US$50. Bump this up if your team plans to generate a lot of content in a month.
- **Per-course cap** — default US$5. Stops a single course from running away with the whole budget if something goes wrong.
- **Alert threshold** — default 80%. When your monthly spend hits this, IFPI emails all admins so you can decide whether to raise the cap or pause work.

You can see your live spend on the `Tokens` page — there's a 14-day chart showing your spend against your budget line.

## D.2 — Picking the right AI for each job

IFPI supports different AI providers for different jobs. The defaults are sensible; only change them if you have a strong preference.

- **Course & slide generation** — GPT-4o (fast and reliable). Alternatives: Claude 4.5, Gemini 3 Pro.
- **Flashcards** — GPT-4o-mini (cheap, good enough). Alternative: Claude Haiku.
- **Voice narration** — OpenAI TTS (natural-sounding, auto-detects the language).
- **Infographics & certificate banners** — Nano Banana (Google's image model).
- **Video overviews** — Sora 2 (the OpenAI video model).
- **Deep research** — Tavily (needs a separate API key — see below).
- **AI Tutor answers** — GPT-4o.

## D.3 — Deep research (optional)

If you want IFPI's AI to be able to search the live web when building a course (e.g. "generate a course on the latest 2026 GDPR amendments"), you need a **Tavily API key**.

Get one from tavily.com, paste it into `Settings → Integrations → Tavily`, and the "Deep Research" button appears in the Course Builder. Without it, the AI uses only your uploaded reference documents.

## D.4 — Multi-language narration

IFPI's AI narration works in 8 languages out of the box: English, Spanish, French, German, Hindi, Japanese, Portuguese, Chinese. Pick a default language for your academy. Learners can still override it on any individual slide.

<details>
<summary><em>Technical reference for Platform Ops</em></summary>

- Budget enforcement: `services/ai_budget_service.py` — checks before every LLM/media dispatch.
- Model routing: `services/ai_router_service.py`.
- Tavily key: `TAVILY_API_KEY` env var OR self-serve `Settings → Integrations`.
- All other AI providers use the Emergent LLM Key (single key, multi-provider).
- Cost ledger table: `ai_usage_ledger` — aggregated per-org per billing month.
- Job orchestration: `models/ai.py::AIJob` (PENDING → RUNNING → COMPLETED/FAILED).

</details>

---

# Phase E — Connecting IFPI to Other Systems {#phase-e}

> **In plain English:** How to let other software talk to IFPI. This covers single sign-on (so staff don't need a separate IFPI password), API tokens (for automations), webhooks (getting notified when things happen), and SCORM export (making your courses playable in other learning systems).

## E.1 — Single sign-on from ERP360 {#sso-roles}

**Purpose:** Let your staff sign into IFPI using their ERP360 identity — no second password to manage.

**How to switch it on** (this is a Platform Ops job, not something you do from the dashboard):
1. Ops adds three settings to IFPI's config: `SSO_ENABLED=true`, a shared secret from ERP360, and IFPI's identifier.
2. Ops restarts the backend.
3. You verify by clicking `Profile → Sign-in methods` — you should see "Single sign-on: enabled".

**What your users see afterwards:**
1. They log into ERP360 as usual.
2. They click the "Open Learning Academy" tile.
3. They land in IFPI already signed in. No IFPI password ever created.

**How roles are translated:**
- ERP360's OWNER, SUPER_ADMIN, ADMIN, MANAGER → IFPI's **Admin**
- ERP360's TRAINER → IFPI's **Instructor**
- ERP360's VIEWER, RECEPTION, MEMBER → IFPI's **Learner**
- Anyone unrecognised → **Learner** (safe default)

## E.2 — API tokens (for automation)

If your team has scripts, spreadsheets, or third-party tools that need to read from or write to IFPI, they need an **API token**.

Go to `Tokens → New Token`, give it a name (so you remember what it's for), and pick scopes:
- **read:catalog** — read your public course catalogue.
- **read:analytics** — read dashboards and spend figures.
- **write:courses** — create/edit courses and slides.
- **write:learners** — bulk-invite learners, create users.
- **sign:webhooks** — validate incoming webhooks from IFPI.

⚠️ **The token is shown once, at creation.** Copy it immediately into wherever it needs to go. If you lose it, revoke it and generate a new one.

The `Tokens` page also shows a live chart of how each token is being used, so you can spot abuse.

## E.3 — Outgoing webhooks

A **webhook** is IFPI phoning your other systems when something happens. Perfect for keeping ERP360 in sync, updating a CRM, or triggering a Slack message.

Go to `Webhooks → New Subscription`, paste a URL where you want the notifications sent, and pick which events matter to you:
- **course.published** — someone published a new course
- **enrollment.completed** — a learner finished a course
- **certificate.issued** — a certificate was awarded
- **certificate.revoked** — a certificate was revoked
- **learner.invited** — someone was invited into the academy
- **ai.spend.threshold** — you hit your AI spending alert threshold

Each notification is cryptographically signed so your receiving system knows it really came from IFPI. If your endpoint fails, IFPI retries with exponential backoff for up to 24 hours before giving up.

## E.4 — Exporting courses as SCORM / xAPI

If you sell training to another organisation and they want to host it in *their* learning system, you can export your course as a **SCORM package**. It's the industry-standard format that Cornerstone, Moodle, TalentLMS, and most enterprise LMSes accept.

From any course: `Course → Publish → SCORM → Download`. IFPI generates a ZIP file that the other system can import directly.

xAPI (Tin Can) statements are also collected automatically as learners take your courses, so you have a modern activity log alongside the older SCORM format.

## E.5 — Standalone or paired with ERP360

IFPI runs happily either way — no code changes needed:

- **Standalone** — the default. Users have their own IFPI passwords, invitations are by email.
- **Paired with ERP360** — SSO is on, users appear automatically when they click through from ERP360, and (optionally) billing routes back to ERP360's lite-billing module.

Ask Platform Ops which mode makes sense for your rollout.

<details>
<summary><em>Technical reference for Platform Ops</em></summary>

- SSO env vars: `SSO_ENABLED`, `ERP360_SSO_SHARED_SECRET`, `SSO_ISSUER`, `SSO_AUDIENCE`.
- Handshake: HS256 JWT with claims `iss, aud, sub, email, name, roles, iat, exp (60s), jti`. Verified against replay via `sso_jti_seen` table.
- Exchange endpoint: `POST /api/auth/sso-exchange`.
- API token model: `models/integrations.py::ApiToken`. SHA-256 hashed at rest; only prefix stored for UI display.
- Webhook model: `WebhookSubscription` + `WebhookDelivery`. HMAC-SHA256 signature in `X-IFPI-Signature` header.
- Retry schedule: exponential backoff, 24h max, dead-lettered after.
- SCORM export: `POST /api/courses/{id}/export-scorm`. Runtime shim at `/api/scorm/runtime.js`.
- Full event catalogue: `docs/IFPI_WEBHOOK_EVENTS.md`.

</details>

---


# Phase F — Certificates, Public Sharing & Data Rules {#phase-f}

> **In plain English:** This is where you decide (a) how the world verifies a certificate you've issued, (b) whether outsiders can browse your course catalogue without logging in, and (c) how long we keep learner data before we delete it.

---

## F.1 — Making certificates trustworthy

Every certificate IFPI issues is designed to be **impossible to fake**. Here's what a recipient (or their future employer) gets:

- **A unique 22-character code** printed on the certificate — think of it like a passport number.
- **A hidden digital signature** built in — anyone can check it's genuine, but nobody can forge one.
- **A QR code** on the PDF. Point a phone camera at it and it opens the verification page automatically.
- **A public link** anyone can visit to confirm the certificate is real. No login needed.

The verification page shows: **who the certificate was issued to, which course they completed, and when.** That's it — no other personal info leaks.

**Protection against abuse:** the public verification page allows 30 checks per minute per visitor. Enough for a recruiter checking a candidate; not enough for someone scraping the site.

---

## F.2 — Letting outsiders browse your courses

You can turn on a **Public Catalogue** so people can see what courses you offer without needing an account. Useful for:
- Sales & marketing pages
- Recruitment ("what training does IFPI provide?")
- Regulators checking your programme

**How to switch it on:** `Organisation Settings → Public Access → Enable`.

**What visitors see:**
- Only **Published** courses appear (drafts and archived courses stay hidden)
- They can browse, but can't enrol — enrolling still requires signing up
- They can also verify a certificate they've been shown, using the same public catalogue page

**How to switch it off:** flip the same toggle back to off. Everything becomes login-only again immediately.

---

## F.3 — How long we keep data (GDPR / POPIA)

Different types of information are kept for different reasons. Here's the shape of it in plain English:

- **Learner personal details** (name, email, profile) — kept for **7 years after they last used the platform**, then only the Owner can permanently delete them. Every delete is written to the audit log.
- **Certificates** — kept **forever**, because the whole point is that they can still be verified 20 years later. If you need to invalidate one (e.g. plagiarism found after the fact), use **Revoke** — the certificate stays in the system but marked as revoked, and the PDF cannot be re-downloaded.
- **AI conversation logs & prompts** — automatically deleted **after 90 days**. No manual clean-up needed.
- **Audit log** (record of who did what, when) — kept for **3 years**. Users cannot delete their own audit entries; only Platform Ops with database access can.

### What learners can do themselves (Iter 33)

Users no longer need to email support to exercise their data rights. From `Profile → Privacy` they can:

- **Download a copy of everything** — one click, gets a ZIP containing their profile, enrolments, certificates, flashcard progress and audit trail as JSON files.
- **Request account deletion** — click delete, receive a 6-digit code by email (expires in 10 minutes), enter the code, done. All personal details are wiped; certificates remain verifiable but show "IFPI Learner" instead of the person's name.

### Bulk certificate operations (for admins)

If an entire cohort's certificates need to be revoked or reactivated (e.g. an accreditation issue), you can do it in one go from `Certificates → Bulk actions`:

- **Revoke many** — up to 500 at once. Skips any already revoked (safe to re-run).
- **Un-revoke many** — the reverse, in case the revocation was a mistake.
- **Re-email download links** — sends every affected holder a fresh email.
- **Download a ZIP of PDFs** — up to 100 certificates bundled into one file.

Every bulk action requires typing a confirmation word and adding a reason, and all of it goes into the audit log.

### Monthly compliance report

If your team has enabled it, IFPI automatically **emails a monthly PDF summary** to whoever you've listed. It covers: active users, certificates issued and revoked in the month, deletion requests, failed logins, and the most common admin actions. Nothing to schedule — it just arrives.

---

## F.4 — Motivation & engagement (streaks, badges, digests)

Under `Organisation Settings → Gamification` you have three levers to keep learners engaged:

- **Daily streaks** — counts consecutive days a learner has been active. Resets at midnight in your organisation's timezone. Shown on their dashboard.
- **Badges** — automatically awarded for milestones (finish a course, get 100% on an exam, complete 5 courses, etc.). Badge names and thresholds are configurable per organisation.
- **Weekly cohort digest** — a friendly recap email sent every Monday morning to every learner in a cohort, showing what their peers achieved and nudging them toward what's next.

All three are opt-in for the learner (they can silence digests from `Profile → Notifications`).

---

# Phase G — Going Live in Production (Platform Ops) {#phase-g}

> **In plain English:** This phase is for whoever is *deploying* IFPI to the internet. If you're an academy admin, you can skip it — your Platform Ops team handles this. It covers the config that must be right before you accept real users, the monitoring wired in for you, and the rescue tools when things go wrong.

**Status:** hardened in Iter 32. All items below are **required** before flipping the tenant to a public URL.

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
- **`AUTH_COOKIE_SECURE=true`** — MUST be `true` in any HTTPS deployment (Iter 33e). Modern browsers silently drop the `Secure`-less auth cookie on HTTPS in many contexts, which shows up as "login succeeds then the very next request 401s." Set to `false` only for local HTTP dev.
- `AUTH_COOKIE_SAMESITE=lax` (default) — flip to `none` **only** if the frontend and API are on different subdomains AND you're also setting `Secure=true`.

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
| Login succeeds but the next API call 401s | `AUTH_COOKIE_SECURE=false` on an HTTPS deployment — browser dropped the cookie | Set `AUTH_COOKIE_SECURE=true` in `.env`, restart backend, hard-refresh browser (Iter 33e) |
| "Change password page disappears" | Fixed in Iter 33d — API interceptor no longer bounces users off auth-flow pages | If still happening, hard-refresh; you're on a stale bundle |
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
