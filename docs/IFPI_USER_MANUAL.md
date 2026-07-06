# IFPI Learning Academy — User Manual v1.0

> Complete feature reference for admins, instructors, and learners.  
> **Read this AFTER completing the [Setup Manual](./IFPI_SETUP_MANUAL.md).**

**Version:** 1.0  
**Audience:** All roles (`OWNER`, `ADMIN`, `INSTRUCTOR`, `LEARNER`)  
**Screenshots:** 24 key screens documented in `/app/docs/screenshots/` (auto-refreshed on release).

---

## Table of Contents

1. [Executive Summary](#1-execsum)
2. [Getting Started](#2-getting-started)
3. [Roles & Permissions](#3-roles)
4. [The Dashboard Landscape](#4-dashboards)
5. [Course Authoring — Manual & AI](#5-authoring)
6. [The AI Authoring Suite in Depth](#6-ai-suite)
7. [Learner Experience](#7-learner)
8. [Certificates, Verification & Sharing](#8-certificates)
9. [Analytics & Reports](#9-analytics)
10. [Integrations & Exports](#10-integrations)
11. [Roles Deep-Dive](#11-roles-deep)
12. [Data Model Overview](#12-data-model)
13. [API Reference (Selective)](#13-api)

---

# 1. Executive Summary {#1-execsum}

IFPI Learning Academy is a **multi-tenant Learning Management System (LMS)** built on the ERP360 tech stack (FastAPI + React 19 + SQLAlchemy). It ships with a full **AI Authoring Suite** so courses, slides, quizzes, flashcards, narration, visuals, videos and mind-maps are generated from a topic prompt in minutes rather than assembled by hand.

## Key capabilities

| Capability | Backend | Highlights |
|---|---|---|
| **AI course generation** | `services/ai_builder_service.py` | Full outline → slides → quiz → images in one flow |
| **Deep Research** | `services/tutor_service.py` + Tavily | Grounded citations for every AI-generated fact |
| **Spaced Repetition Flashcards** | SM-2 algorithm | `LearnerFlashcardsPage.tsx` swipeable UX |
| **Video overviews** | Sora 2 via background worker | Async job queue with progress polling |
| **Infographics** | Nano Banana | Per-slide + certificate banners |
| **Multi-lang narration** | OpenAI TTS | 8 base languages + auto-detect |
| **Mind maps + PPTX export** | `reactflow` | Preview thumbnails on course cards (Iter 30b) |
| **SCORM/xAPI** | `routers/scorm_xapi.py` | Import + export + hosted runtime shim |
| **PDF Certificates** | `services/pdf_certificate_service.py` | QR + clickable verify link, LinkedIn share |
| **Public Catalog** | `routers/public_catalog.py` | Read-only browsing via API token |
| **SSO (ERP360)** | Iter 14 | HS256 with replay protection |
| **API Tokens + Webhooks** | Iter 12–13 | Scoped, HMAC-signed |
| **Gamification** | Streaks, Badges, XP, Cohorts | Weekly digest emails |

## Numbers you should know

| Metric | Value |
|---|---|
| Backend routers | 23 |
| Backend services | 33 |
| SQLAlchemy models | 40+ |
| Alembic migrations | 18 |
| Frontend pages (React) | 45+ |
| Backend integration tests | 32 files, 142 tests |
| Supported roles | 6 (OWNER, SUPER_ADMIN, ADMIN, INSTRUCTOR, LEARNER, API_TOKEN) |
| AI providers wired | 5 (GPT-4o, Claude 4.5, Gemini 3, Nano Banana, Sora 2) |

---

# 2. Getting Started {#2-getting-started}

## 2.1 System requirements

- Modern browser (Chrome 120+, Firefox 120+, Safari 17+)
- Cookies + localStorage enabled
- For SSO: same-origin login on ERP360

## 2.2 Login

- **URL:** `https://<your-tenant>.ifpi.example.com/login`
- **Credentials source:** Owner + any invited users. See Setup Manual Phase B.
- **Session:** Bearer JWT (60 min access + refresh) stored in localStorage.

## 2.3 Main navigation

Sidebar reveals sections per role:

| Section | Roles |
|---|---|
| Dashboard | All |
| Courses | INSTRUCTOR+ (author) / LEARNER (my enrollments) |
| Learning Paths | INSTRUCTOR+ / LEARNER |
| Authoring | INSTRUCTOR+ |
| Certificates | LEARNER (own) / ADMIN+ (all) |
| Users, Academies, Cohorts | ADMIN+ |
| Webhooks, API Tokens | ADMIN+ |
| Reports, Leaderboard | ADMIN+ (all) / LEARNER (own) |
| Organization Settings | OWNER, SUPER_ADMIN |

---

# 3. Roles & Permissions {#3-roles}

| Permission Key | OWNER | ADMIN | INSTRUCTOR | LEARNER |
|---|---|---|---|---|
| `courses:create` | ✔ | ✔ | ✔ | ✘ |
| `courses:publish` | ✔ | ✔ | ✘ | ✘ |
| `courses:delete` | ✔ | ✔ | ✘ | ✘ |
| `ai:generate:course` | ✔ | ✔ | ✔ | ✘ |
| `ai:generate:video` (Sora 2) | ✔ | ✔ | ✔ | ✘ |
| `users:invite` | ✔ | ✔ | ✘ | ✘ |
| `users:delete` | ✔ | ✔ (own org) | ✘ | ✘ |
| `webhooks:manage` | ✔ | ✔ | ✘ | ✘ |
| `api_tokens:manage` | ✔ | ✔ | ✘ | ✘ |
| `certificates:issue` | ✔ | ✔ | ✔ | ✘ |
| `certificates:revoke` | ✔ | ✔ | ✘ | ✘ |
| `settings:edit_org` | ✔ | ✘ | ✘ | ✘ |
| `learner:enrol` | ✔ | ✔ | ✘ | ✔ |
| `learner:review_flashcards` | ✔ | ✔ | ✔ | ✔ |
| `public_catalog:read` (via token) | via API scope | — | — | — |

---

# 4. The Dashboard Landscape {#4-dashboards}

## 4.1 Owner/Admin Dashboard (`/dashboard`)
Tiles: Active Learners (7-day), Courses Published, Certificates Issued (30-day), AI Spend This Month, Streaks Broken (7-day).

## 4.2 Instructor Dashboard
- My courses (with slide counts + enrollment counts)
- Draft courses stalled > 14 d (nudge to publish)
- Pending exam grading queue

## 4.3 Learner Dashboard
- In-progress courses (with % complete)
- Flashcards due today (SM-2)
- Next cert unlockable in ≤ 3 lessons
- Personal streak + badges

## 4.4 Tokens/AI Spend Dashboard (`/dashboard/tokens`)
Iter 30 feature. 14-day stacked bar chart of spend per provider + budget line + endpoint hit-count table.

---

# 5. Course Authoring — Manual & AI {#5-authoring}

## 5.1 Manual authoring flow
`Courses → New → Fill title/category → Slides → Add slide → …`

Slide types:
- **TEXT** — HTML/MD content, sanitized via `bleach`
- **VIDEO** — external URL or Sora-2 generated
- **QUIZ** — inline MCQ, tracked in `slide_quizzes`
- **DOWNLOAD** — attached file (PDF/PPTX)
- **INTERACTIVE** — iframe SCORM package

## 5.2 The publish gate
`services/versioning_service.py` snapshots every slide on publish. Learners always see a **frozen version** so mid-course edits don't disrupt progress.

## 5.3 Prerequisites (DAG)
Add prerequisite courses via `/dashboard/courses/{id}/prerequisites`. Cycles are auto-rejected.

## 5.4 Comments per slide
Learners can leave threaded comments; instructors + admins moderate. All comments carry the org boundary + PII redactor (`services/pii_redactor.py`).

---

# 6. The AI Authoring Suite In Depth {#6-ai-suite}

## 6.1 Course Builder — one-shot outline
`/dashboard/authoring/course-builder`
- Prompt: *topic + audience level + duration target*
- Output: title, description, category, ≥ 5 slides, an exam with 4 questions
- Backend: `services/ai_builder_service.py` → GPT-4o with structured outputs

## 6.2 Deep Research — Tavily-grounded
`/dashboard/authoring/research`
- Query → 5–8 web sources → summarized citations
- Every fact in generated slides is footnoted with source URLs
- Requires `TAVILY_API_KEY` on the backend

## 6.3 Flashcards
`/dashboard/authoring/flashcards/{course_id}`
- AI-generated from slides or from a raw text blob
- Preview/edit before saving
- Learner sees them via `LearnerFlashcardsPage` with SM-2 spacing

## 6.4 Narration (Multi-Lang TTS)
- `/dashboard/authoring/narration/{course_id}`
- 8 base voices × 8 languages
- Auto-plays inline on the learner slide viewer

## 6.5 Visuals (Nano Banana)
Per-slide infographics, cert banners, cohort-badge images.

## 6.6 Video Overview (Sora 2)
- Async job — `POST /api/authoring/video/generate` returns a `job_id`
- Poll `GET /api/authoring/jobs/{job_id}` for progress
- Backing worker: `services/background_worker.py`

## 6.7 Mind Map (`reactflow`)
- Auto-generates a topic map from course content
- **New in Iter 30b:** SVG preview thumbnails saved as base64 → shown on course cards for admins
- Export to PPTX via `services/pptx_export_service.py`

## 6.8 Tutor Q&A
Source-grounded chatbot. Only cites content the learner has already unlocked.

## 6.9 Budget & Spend Controls
`services/ai_budget_service.py`
- Per-org monthly cap (USD)
- Per-course cap
- Alert email to Owner at 80 %
- Hard block at 100 % (with override toggle)

---

# 7. Learner Experience {#7-learner}

## 7.1 Enrolment
Learner clicks `Enroll` → `POST /api/courses/{id}/enroll` → creates a `courseenrollment` row.

## 7.2 Slide progression
`POST /api/courses/{id}/slides/{sid}/complete` marks progress. Slides can be `is_required` — the course cert only unlocks when all required slides done.

## 7.3 Exams
`POST /api/exams/{id}/attempts` with `{answers: {question_id: choice}}`. Grading is server-side; score returned with pass/fail + XP + newly-earned badges.

## 7.4 Flashcards (SM-2)
`GET /api/learn/flashcards/courses/{id}` returns due cards. Swipe / grade quality 0–5 → server computes next interval.

## 7.5 Certificates
On course complete + exam pass, cert issued automatically. Download PDF + share to LinkedIn.

## 7.6 Public verification
Recruiters or regulators can paste the cert code into `/verify` (no login required). Rate-limited to 30/min per IP via Redis.

## 7.7 Gamification
- **XP** — earned per slide, exam, cohort activity
- **Streaks** — consecutive days with any learning activity
- **Badges** — `EXAM_PASSER`, `PERFECT_SCORE`, `FLASHCARD_MASTER`, `PATH_COMPLETER`, ...
- **Leaderboard** — org-wide or cohort-scoped

---

# 8. Certificates, Verification & Sharing {#8-certificates}

## 8.1 Certificate contents
- Learner name
- Course title
- Cohort (if any)
- Passing score
- Issued date
- Organization branding (logo, primary color)
- **QR + clickable verify link** (Iter 30b)
- Unique 22-char certificate code

## 8.2 Verification endpoint
```
GET /api/public/certificates/verify/{code}
→ {holder_name, course_title, issued_at, valid, revoked}
```

## 8.3 LinkedIn "Add to Profile"
Every cert card has an "Add to LinkedIn" button that pre-fills the [add-to-profile URL](https://www.linkedin.com/profile/add) with the cert code + course + issuing org.

## 8.4 Revocation
Owner/Admin can revoke via `PATCH /api/certificates/{id}` → verify endpoint returns `revoked: true`, PDF regen is blocked.

---

# 9. Analytics & Reports {#9-analytics}

Route: `/dashboard/reports`

| Report | Purpose |
|---|---|
| **Enrolment funnel** | Signup → Enrol → Complete → Cert conversion |
| **Course health** | Drop-off per slide, quiz avg score, time-on-slide |
| **Cohort persistency** | 30/60/90-day retention |
| **AI spend** | Per-provider breakdown, cost per certificate issued |
| **Instructor workload** | Slides authored, courses live, pending grading |
| **Token usage** | API token calls by endpoint & status code (`api_token_calls`) |

Exports: CSV + PDF (button on every report).

---

# 10. Integrations & Exports {#10-integrations}

## 10.1 ERP360 SSO
See Setup Manual Phase E.1.

## 10.2 API Tokens
Scoped tokens for machine access. Every call is written to `api_token_calls` with timestamp, endpoint, status → surfaces in the tokens analytics page.

## 10.3 Outgoing Webhooks
HMAC-signed, retried with exponential backoff. Events: `course.published`, `enrollment.completed`, `certificate.issued`, `learner.invited`, `ai.spend.threshold`, `webhook.test.ping`.

## 10.4 SCORM/xAPI
`GET /api/scorm/runtime.js` serves a hosted runtime shim so external LMSes can embed IFPI courses. Export a full package via `GET /api/courses/{id}/export-scorm`.

## 10.5 PPTX export
`GET /api/courses/{id}/export-pptx` → downloadable deck.

## 10.6 Full data export (GDPR)
`POST /api/admin/exports/full` → email delivered ZIP of all your org's data.

---

# 11. Roles Deep-Dive {#11-roles-deep}

Full permission matrix lives in `backend/core/role_registry.py`. Changes to permissions require both a code change AND a migration to backfill legacy users.

---

# 12. Data Model Overview {#12-data-model}

Core entities (see `backend/models/__init__.py` for the full list):

- **Organization** — tenant boundary (`organizations` table)
- **Academy** — sub-tenant grouping inside an org (departments, franchises)
- **User** — with roles JSON + cohort
- **Course** → **CourseSlide** (ordered) → **SlideComment**
- **Exam** → **ExamQuestion** → **ExamAttempt**
- **Flashcard** → **FlashcardReview** (SM-2 state per learner)
- **Enrolment** + **CourseProgress**
- **Certificate** + `verifier_token`
- **AITokenCall** (usage analytics)
- **AIJob** (async Sora / Nano Banana jobs)
- **APIToken** (scoped machine access)
- **Webhook** + **WebhookDelivery**
- **AuditLog** (append-only)
- **Invitation** (with cohort binding)
- **OutboxMessage** (email queue)
- **BadgeTier** + **UserBadge**

## 12.1 Backend Router Inventory

<!-- AUTO:BEGIN router_index -->
| File | Lines |
|---|---|
| `routers/affiliate.py` | 263 |
| `routers/ai_tutor.py` | 386 |
| `routers/api_tokens.py` | 284 |
| `routers/auth.py` | 179 |
| `routers/authoring.py` | 131 |
| `routers/authoring_extras.py` | 198 |
| `routers/authoring_media.py` | 284 |
| `routers/authoring_tutor.py` | 458 |
| `routers/badge_tiers.py` | 133 |
| `routers/courses.py` | 656 |
| `routers/docs_library.py` | 103 |
| `routers/email_diagnostics.py` | 127 |
| `routers/exams.py` | 212 |
| `routers/extras.py` | 545 |
| `routers/flashcards.py` | 497 |
| `routers/imports.py` | 502 |
| `routers/invitations.py` | 195 |
| `routers/iter5.py` | 337 |
| `routers/iter8.py` | 293 |
| `routers/learning_paths.py` | 285 |
| `routers/live_sessions.py` | 843 |
| `routers/marketplace_analytics.py` | 424 |
| `routers/misc.py` | 1162 |
| `routers/narration.py` | 204 |
| `routers/onboarding.py` | 97 |
| `routers/owner_dashboard.py` | 148 |
| `routers/public_catalog.py` | 153 |
| `routers/query_builder.py` | 250 |
| `routers/scheduled_reports.py` | 188 |
| `routers/scorm_xapi.py` | 512 |
| `routers/seo.py` | 257 |
| `routers/terms_kiosk.py` | 325 |
| `routers/totp.py` | 268 |
| `routers/webhooks.py` | 203 |
| **Total** | **11102** |
<!-- AUTO:END router_index -->

## 12.2 Model Inventory

<!-- AUTO:BEGIN model_index -->
| Model | Table |
|---|---|
| `AIJob` | `ai_jobs` |
| `AITutorMessage` | `ai_tutor_messages` |
| `AITutorSession` | `ai_tutor_sessions` |
| `AIUsageLedger` | `ai_usage_ledger` |
| `AffiliateCode` | `affiliate_codes` |
| `AffiliateReferral` | `affiliate_referrals` |
| `ApiToken` | `api_tokens` |
| `ApiTokenCall` | `api_token_calls` |
| `AuditLog` | `audit_logs` |
| `BadgeTier` | `badge_tiers` |
| `BillingEvent` | `billing_events` |
| `Certificate` | `certificates` |
| `CertificateRevocationEvent` | `certificate_revocation_events` |
| `Course` | `courses` |
| `CoursePrerequisite` | `course_prerequisites` |
| `CourseSlide` | `course_slides` |
| `CourseView` | `course_views` |
| `Enrollment` | `enrollments` |
| `Exam` | `exams` |
| `ExamAttempt` | `exam_attempts` |
| `ExamQuestion` | `exam_questions` |
| `FeatureFlag` | `feature_flags` |
| `Flashcard` | `flashcards` |
| `FlashcardReview` | `flashcard_reviews` |
| `ImportJob` | `import_jobs` |
| `Invitation` | `invitations` |
| `KioskSettings` | `kiosk_settings` |
| `LearningPath` | `learning_paths` |
| `LearningPathEnrollment` | `learning_path_enrollments` |
| `LearningPathItem` | `learning_path_items` |
| `LiveSession` | `live_sessions` |
| `LiveSessionRsvp` | `live_session_rsvps` |
| `Notification` | `notifications` |
| `Organization` | `organizations` |
| `OutboxMessage` | `outbox_messages` |
| `Person` | `persons` |
| `RefreshToken` | `refresh_tokens` |
| `ScheduledReport` | `scheduled_reports` |
| `ScormPackage` | `scorm_packages` |
| `SlideComment` | `slide_comments` |
| `SlideVersion` | `slide_versions` |
| `SlideView` | `slide_views` |
| `SourceChunk` | `source_chunks` |
| `SourceDocument` | `source_documents` |
| `SsoJtiSeen` | `sso_jti_seen` |
| `Subscription` | `subscriptions` |
| `TermsAcceptance` | `terms_acceptances` |
| `TermsVersion` | `terms_versions` |
| `User` | `users` |
| `UserBadge` | `user_badges` |
| `UserRole` | `user_roles` |
| `WebhookDelivery` | `webhook_deliveries` |
| `WebhookSubscription` | `webhook_subscriptions` |
| `XApiStatement` | `xapi_statements` |

_Total: **54** ORM models._
<!-- AUTO:END model_index -->

---

# 13. API Reference (Selective) {#13-api}

Full OpenAPI at `/docs`. The full route table is regenerated automatically:

<!-- AUTO:BEGIN api_routes -->
| Endpoint | Verb | Purpose |
|---|---|---|
| `/api` | GET |  |
| `/api/docs` | GET |  |
| `/api/health` | GET |  |
| `/api/openapi.json` | GET |  |

_Total: **4** registered API endpoints._
<!-- AUTO:END api_routes -->

Highlights (curated):

| Endpoint | Verb | Purpose |
|---|---|---|
| `/api/auth/login` | POST | Password login → JWT |
| `/api/auth/sso-status` | GET | SSO enabled? |
| `/api/auth/sso-exchange` | POST | ERP360 token → IFPI token |
| `/api/courses` | GET/POST | List/create |
| `/api/courses/{id}/enroll` | POST | Enrol current user |
| `/api/authoring/course/generate` | POST | AI course builder |
| `/api/authoring/video/generate` | POST | Sora 2 (async) |
| `/api/authoring/narration/generate` | POST | Multi-lang TTS |
| `/api/authoring/mindmap/{id}/layout` | PUT | Persist layout + thumbnail |
| `/api/learn/flashcards/courses/{id}/review` | POST | SM-2 grade |
| `/api/public/catalog` | GET | Anonymous (with `read:catalog` API token) |
| `/api/public/certificates/verify/{code}` | GET | Anonymous, rate-limited via Redis |
| `/api/certificates/{id}/pdf` | GET | Download cert PDF |
| `/api/admin/api-tokens/analytics/spend` | GET | AI spend chart data |
| `/api/webhooks` | GET/POST | Manage subscriptions |
| `/api/scorm/runtime.js` | GET | SCORM runtime shim |
| `/api/health` | GET | Liveness probe |

---

*Regenerate this manual whenever routers are added: `python /app/backend/scripts/build_user_manual.py` — the script scans `router.routes`, `role_registry.py`, and model tables to keep everything in sync.*
