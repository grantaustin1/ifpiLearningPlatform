# IFPI Learning Academy — Staff Handbook

> **A friendly walk-through of IFPI Learning, written for the people who actually use it every day.**

**Who this is for:** Frances, the content team, instructors, learners — anyone who signs into IFPI to do work. If you're deploying the platform to a server, read the Setup Manual instead.

**How to read it:** Start with "Getting In." Everything else you can dip into when you need it. Every section has screenshots of the actual screens so you know what to look for.

---

## What's inside

1. [Getting In — logging in the first time](#2-getting-started)
2. [Your Dashboard — what everything means](#4-dashboards)
3. [Building a Course — manually or with AI](#5-authoring)
4. [The AI Authoring Suite — every generator explained](#6-ai-suite)
5. [What Learners See — the other side of the app](#7-learner)
6. [Certificates — issuing, sharing, revoking](#8-certificates)
7. [Reports and Analytics](#9-analytics)
8. [Sharing with Other Systems](#10-integrations)
9. [Your Account — profile, password, privacy](#account-self)
10. [Where to Find These Manuals in the App](#15-docs-library)

> *Technical appendix (§11–14) — reference material for developers and Platform Ops. Feel free to skip if you're not a coder.*

---

# 1. What IFPI Learning Is, In Two Paragraphs

IFPI Learning Academy is a place where your organisation runs its training. You build courses, invite learners, they watch videos and take quizzes, they earn certificates, you see reports of how they're doing. That's it in a sentence.

What makes IFPI unusual is the **AI Authoring Suite**. Instead of writing every slide by hand, you can hand IFPI a topic ("Introduction to Music Copyright") and it drafts the entire course for you — outline, slides, quiz questions, flashcards, even narration and a short video summary. You edit anything you don't like. What used to take a full week of a content designer's time now takes an afternoon.


| Webhooks, API Tokens | ADMIN+ |
| Reports, Leaderboard | ADMIN+ (all) / LEARNER (own) |
| Organization Settings | OWNER, SUPER_ADMIN |

---

# 2. Getting In — Your First Sign-In {#2-getting-started}

## 2.1 What you need

- A modern web browser (Chrome, Edge, Firefox or Safari from the last two years)
- Cookies enabled (they are by default — you'd know if they weren't)
- The web address, email, and password IFPI Platform Ops emailed you

## 2.2 The login screen

Type the web address into your browser (it looks like `https://your-academy.ifpi.example.com/login`). You'll see this:

![The IFPI login screen](screenshots/01_login.png)

Type your email in the top box, your password in the bottom box, and click **Sign in**.

## 2.3 If it's your first time — change the password

The first password IFPI gave you is temporary. As soon as you sign in, IFPI will show you a screen asking you to pick a new one.

- Type the temporary password in "Current password"
- Type a new password (at least 8 characters, different from the old one) in "New password"
- Type the same new password again in "Confirm new password"
- Click **Save new password**

You'll land on your dashboard. **Write down your new password somewhere safe** — IFPI can email you a reset link if you forget, but only if the email on your account is correct.

## 2.4 If you forget your password

On the login screen, click **"Forgot your password?"**. Type your email, hit send, check your inbox. There'll be a link that's good for 24 hours — click it, pick a new password, done.

If the email never arrives (check your spam folder first), contact whoever set up your IFPI account. They have a rescue tool.

## 2.5 Signing out

Click your name in the bottom-left corner, then **Sign out**. Always do this on a shared computer.

---

# 3. Who Can Do What (Roles) {#3-roles}

Everyone in IFPI has a **role**. Your role decides what you see when you sign in. There are five:

- **Admin** — you can do everything: invite people, build courses, publish them, issue certificates, see all the reports. This is what senior IFPI staff have.
- **Instructor** — you can build courses and grade learners. You can't invite new members or see billing.
- **Learner** — the most common role. You take courses, sit exams, earn certificates. You don't see any admin screens.
- **Billing Viewer** — read-only look at invoices and spend. For finance staff who don't build content.
- **Super Admin** — reserved for IFPI Platform Ops. Manages every academy on the platform.

People can hold more than one role if they need to (e.g. an instructor who also enrolls in colleagues' courses).

---

# 4. Your Dashboard — What Everything Means {#4-dashboards}

The dashboard is the first thing you see when you sign in. What appears there depends on your role.

## 4.1 What Admins see

![The Admin dashboard](screenshots/03_dashboard_admin.png)

Going around the screen:

- **Four numbers at the top** — Active Learners, Courses Published, Certificates Issued, and AI Spend This Month. These give you the health of your academy in one glance.
- **Onboarding progress** — a percentage showing how much of the initial setup you've completed. Click it to see the checklist.
- **Members needing action** — learners who've stalled: not signed in for 2 weeks, failed an exam, have a certificate about to expire, etc. Click any row to jump to that person.
- **Docs opened this week** — how many times your team has read the setup and user manuals (the ones you're reading right now). Handy for spotting who might need help.
- **Quick actions** — coloured shortcut tiles for common jobs: build a course, invite members, view reports, open the AI suite.

## 4.2 What Instructors see

Same shape as the admin dashboard, but with fewer tiles — no billing figures, no invite-members button. Focused on the courses you own and the learners taking them.

## 4.3 What Learners see

![The learner dashboard](screenshots/20_learner_dashboard.png)

- **My Courses** — cards for every course you're enrolled in. Click one to pick up where you left off.
- **Streak counter** — how many days in a row you've been active. Great gamification.
- **Certificates** — your earned certificates, ready to download or share.
- **Flashcards due today** — quick-review deck powered by spaced repetition.

## 4.4 Watching your AI spend

If your academy uses the AI Authoring Suite, keep an eye on `Tokens & Spend` in the sidebar. It shows a rolling 14-day chart of how much AI content generation is costing you, against your monthly cap.

---

# 5. Building a Course {#5-authoring}

## 5.1 The two ways to build

Every course starts with clicking **New Course** from the Courses page.

![The Courses page](screenshots/04_courses_list_admin.png)

From there you have two paths:

- **Build slide-by-slide, by hand** — the traditional way. Best when you already have all your material written and you just need to type it in.
- **Generate the whole thing with AI** — the fast way. Type a topic, IFPI drafts everything, you edit what needs editing. Best when you're starting from scratch.

Most content teams use a mix: AI generates a first draft, humans polish it.

## 5.2 Building a course by hand

Click **New Course**, fill in the title, description, category, and any prerequisites (see next section). Save.

You'll land on the course editor:

![The Course editor](screenshots/05_course_edit.png)

- **Left panel** — the list of slides. Click **+ Add slide** to create one.
- **Middle** — the content editor for the currently selected slide.
- **Right** — settings for this slide (type, ordering, whether it's required).

Slide types you can pick:
- **Text** — write in the box like it's a document. Supports headings, lists, bold, links.
- **Video** — paste a video URL (YouTube, Vimeo, or upload your own).
- **Image** — upload a graphic.
- **PDF** — upload a PDF document.
- **Audio** — for narration or podcasts.
- **SCORM** — upload a pre-built SCORM course package from another system.

Drag slides up and down to reorder. Save as you go.

## 5.3 Adding prerequisites

If Course B should only be available to learners who've finished Course A, add A as a prerequisite of B. Click **Prerequisites → Add**, pick the course, save.

You can chain many prerequisites together. IFPI will refuse to create a loop (A requires B, B requires A) — no headaches.

## 5.4 Letting people comment on slides

Under each slide, learners can leave comments — great for questions or clarifications. Instructors can reply, pin useful threads, and mute problem users. Turn comments off per slide if you want to.

## 5.5 Publishing

Once you're happy, flip the course status from **Draft** to **Published**. IFPI does a quick check first — you need at least one required slide, and if you set a passing score you need a passing exam. If anything's missing it tells you exactly what.

Published courses appear in the catalogue immediately. Learners can now enrol.

---

# 6. The AI Authoring Suite {#6-ai-suite}

This is where IFPI shines. Every tool here saves your content team hours of work. All of these are on the **Authoring** page.

![The AI Authoring hub](screenshots/06_authoring_course_builder.png)

## 6.1 Course Builder — draft a whole course in one shot

Type a topic in the box (e.g. "Introduction to Music Copyright Law for African Producers"), pick the target audience level and length, click **Generate**. IFPI does the rest:

1. Drafts an outline (usually 6-10 slides).
2. Writes each slide's content.
3. Writes a matching quiz with the answer key.
4. Suggests images for each slide.

You review the outline first — reject slides you don't want, tweak the ones you like. IFPI regenerates just those bits. Once you're happy, click **Save all** and the whole course appears in your Courses list, ready to edit or publish.

## 6.2 Deep Research — grounded in real sources

If you're teaching something factual (regulations, industry statistics), turn on **Deep Research**. IFPI's AI will search the live web while drafting, and every claim it makes gets a citation. Learners see the sources on the slide.

Requires a Tavily API key (see Setup Manual Phase D).

## 6.3 Flashcards — spaced repetition study

![Generating flashcards](screenshots/07_authoring_flashcards.png)

Click **Generate flashcards** on any published course. IFPI reads the slides and produces study cards (question on the front, answer on the back). Learners see these on their dashboard, sorted by which they most need to review — using the SM-2 algorithm, the one Anki uses.

## 6.4 Narration — text becomes voice

For any slide, click **Narrate**. IFPI reads the slide content aloud in a natural voice. Eight languages supported out of the box, and IFPI auto-detects which one to use based on the slide's text.

## 6.5 Visuals — AI-generated images

For any slide, click **Generate visual**. IFPI uses Google's Nano Banana model to produce an image that matches the slide's content. Refresh a few times if the first one isn't quite right.

Also used for certificate banners — see Setup Manual Phase A.

## 6.6 Video overview — Sora 2

Click **Generate video overview** on a course. IFPI produces a ~30-second promotional clip that summarises the course. Useful for your marketing pages or the course catalogue thumbnail. Takes 2-3 minutes to render — IFPI notifies you when it's done.

## 6.7 Mind maps

![The mind-map view](screenshots/08_mindmap.png)

For any course, click **Mind map**. IFPI lays out every slide as a node in an interactive diagram — great for showing learners how the pieces connect. Drag nodes around; the layout saves automatically.

## 6.8 AI Tutor — Q&A for learners

Learners can click **Ask the tutor** on any slide. IFPI reads the whole course and answers their question, citing the specific slide the answer came from. Zero hallucinations.

## 6.9 Keeping AI costs under control

Every generation click costs a few cents. Your budget cap (Setup Manual Phase D) stops it running away. You'll see the live spend on the `Tokens & Spend` page, and IFPI emails all admins when you hit 80% of your monthly cap.

---

# 7. What Learners See {#7-learner}

Now flip perspective — this is what someone with the **Learner** role experiences.

## 7.1 Finding and enrolling in a course

![The learner catalogue](screenshots/21_learner_courses.png)

From their dashboard, learners click **Browse courses**. They see every course you've published, filterable by category. Click a card → **Enrol**. If the course has prerequisites they haven't finished, IFPI politely blocks the enrol and tells them which course they need to complete first.

## 7.2 Taking a slide-by-slide course

![Inside a slide](screenshots/22_slide_view.png)

Learners move through slides one at a time. Progress is saved automatically, so they can close their laptop and resume from the same slide next week. On each slide they can:

- **Ask the AI Tutor** a question about what they just read.
- **Leave a comment** (if you enabled it).
- **Play narration** if you generated it.

The progress bar at the top shows how far they are through the course.

## 7.3 Taking an exam

At the end of a course, if you set a passing score, learners take a summative exam. It can have multiple-choice, true/false, or short-answer questions. IFPI grades automatically (except short-answer, which comes to instructors for manual marking).

If they fail, they can retake (subject to the max-attempts limit you set). Every attempt is recorded.

## 7.4 Flashcards

If you generated flashcards, learners see a "Review flashcards" tile on their dashboard. It shows the cards they most need to review based on how well they remembered them last time (this is spaced repetition — the same technique Anki, Duolingo, and Quizlet use).

## 7.5 Earning a certificate

Once they've completed all required slides AND passed the exam (if there is one), the certificate is generated automatically. They can download it, share it to LinkedIn with one click, or send anyone a public verification link.

## 7.6 Motivation — streaks and badges

Learners see their **daily streak** on the dashboard (consecutive days active). They earn badges for milestones: finishing their first course, getting 100% on an exam, completing a learning path. Weekly digest emails recap what their cohort achieved and nudge them toward what's next.

---


# 8. Certificates, Verification & Sharing {#8-certificates}

# 8. Certificates {#8-certificates}

![The certificates admin page](screenshots/17_certificates_admin.png)

## 8.1 What's on the certificate

Every certificate IFPI issues shows:

- **Learner's name** — the person who earned it
- **Course title** — what they completed
- **Their cohort** — if they were in one (e.g. "Sales 2026 Q1")
- **Passing score** — the mark they achieved
- **Date issued** — when they earned it
- **Your academy's branding** — your logo, your colour, your signature
- **A unique 22-character code** — think of it as the certificate's fingerprint
- **A QR code and clickable link** — for instant verification

The PDF looks like this when downloaded:

![Sample certificate PDF](screenshots/18_cert_pdf.png)

## 8.2 How outsiders verify a certificate

If a recruiter, regulator, or client wants to check a certificate is genuine, they:

1. Scan the QR code with their phone, **or**
2. Type the 22-character code into your academy's `/verify` page

Either way, they see a simple confirmation showing who was awarded the certificate, for which course, and when. That's it — no other personal data is exposed.

## 8.3 Sharing to LinkedIn

Learners see a **"Add to LinkedIn"** button on every certificate they've earned. One click pre-fills the LinkedIn form with the certificate code, course title, and your academy name.

## 8.4 Revoking a certificate

Sometimes you need to invalidate a certificate — plagiarism found after the fact, accreditation issue, etc. **Revoke** does this without deleting anything.

From the **Certificates** page:
- **Revoke one** — click the certificate row, hit **Revoke**, type "REVOKE" to confirm, add a reason. Done. The certificate stays visible but marked "Revoked" and the PDF cannot be re-downloaded.
- **Revoke many at once** — tick the checkboxes on multiple rows, click **Bulk actions → Revoke selected**. Same confirmation.
- **Un-revoke** — if it was a mistake, click **Un-revoke** to bring it back.
- **Re-email download links** — for holders who lost their email.
- **Download a batch as ZIP** — bundle up to 100 certificate PDFs into a single ZIP file for archiving.

Every revoke, un-revoke, or bulk action is logged forever. Nothing is silent.

## 8.5 Monthly compliance report

If enabled, IFPI emails a monthly PDF summary of everything certificate-related to whoever you've listed — certificates issued, revoked, deletion requests, failed login attempts, top admin actions. Nothing to schedule. It just arrives.

---

# 9. Reports and Analytics {#9-analytics}

Under **Reports** in the sidebar, you get a set of pre-built dashboards. Everything can be exported as CSV or PDF.

- **Enrolment funnel** — how many people signed up, enrolled, completed, earned a certificate. Where you're losing them.
- **Course health** — for each course, which slide learners drop off at, average quiz scores, time spent per slide. Tells you which slides need work.
- **Cohort persistency** — 30, 60, 90-day retention. Are the November hires still active in February?
- **AI spend** — how much each AI provider is costing, spend per certificate issued.
- **Instructor workload** — how many courses each instructor owns, how much grading is pending.
- **Token usage** — if you have API tokens (Setup Manual Phase E), see what they're being used for.

---

# 10. Sharing with Other Systems {#10-integrations}

## 10.1 ERP360 SSO
See Setup Manual Phase E.1 for the technical setup — but for staff purposes, once it's enabled you just click through from ERP360 to IFPI and never sign in again.

## 10.2 Talking to IFPI from spreadsheets and scripts (API tokens)

If your team uses spreadsheets that pull IFPI data (e.g. "how many active learners this month?"), or if you want another system to create courses automatically, you'll need an **API token**. See Setup Manual Phase E.2.

Once you have a token, you can share it with your automations. Every call is logged, so if a token is misused you can see it and revoke it.

## 10.3 Getting notified when things happen (webhooks)

If you'd like Slack, Discord, or another system to be notified when a course is published, a certificate is issued, or an AI spend threshold is hit, use **webhooks**. Setup Manual Phase E.3 explains how to point them at your other tools.

## 10.4 Exporting courses to other systems (SCORM)

Selling training to another company? You can export any course as a SCORM package (industry standard). Their learning system will import it as-is. From any course → **Publish → SCORM → Download**.

## 10.5 Exporting a course as a slide deck (PPTX)

Every course can also be downloaded as a PowerPoint presentation — handy for offline presentations or handing content to another platform. Click **Export → PowerPoint** on the course page.

---

# Your Account — Profile, Password, Privacy {#account-self}

This section is for **every user**, whatever their role.

![The Profile page](screenshots/24_profile.png)

## What you can change

Click your name in the sidebar and pick **Profile**. From here:

- **Change your display name** — what appears on your certificates and comments.
- **Upload a profile photo** — appears next to your comments and on the leaderboard.
- **Change your password** — see below.
- **Turn on Two-Factor Authentication** — highly recommended. Uses Google Authenticator or any TOTP app. Setup Manual Phase B.4 explains.
- **Language** — pick your preferred language for the UI (independent of your academy's default).
- **Notifications** — decide which emails you want (weekly digest, cohort recap, streak nudges).

## Change your password

`Profile → Security → Change Password`. Type your current password, then your new one twice. Save. You stay signed in.

If you forgot the current one, sign out, then use the **Forgot password?** link on the sign-in screen.

## Download all your data (GDPR)

Under `Profile → Privacy → Download my data` you can download a ZIP file containing everything IFPI has about you: your profile, enrolments, progress, certificates, flashcard history, and audit trail. Perfect for GDPR "data portability" requests. Zero admin approval needed.

## Delete your account (GDPR Right to Erasure)

Under `Profile → Privacy → Delete my account`:

1. Click **Request deletion**. IFPI emails you a 6-digit code (valid for 10 minutes).
2. Type the code, click confirm.
3. Your personal details are wiped, your sessions and API tokens revoked, and your certificates continue to verify but show "IFPI Learner" instead of your name.

The deletion is permanent. Every step is logged.

## Verify your email

If your email address changes, IFPI will send a verification link to the new one. Until you click it, some sensitive actions are blocked. Look under `Profile → Security → Resend verification` if the email didn't arrive.

---

# 11. Rate Limits & Fair Use

To keep IFPI stable, some pages have gentle rate limits. Most staff never hit them:

- **Signing in** — 5 attempts per minute, 10 per hour on the same email.
- **New account signup** — 3 per hour from the same IP address.
- **Forgot-password requests** — 3 per hour per email address.
- **Email verification resends** — 2 per hour per user.
- **Public certificate verification** — 30 checks per minute per visitor.
- **Public catalogue browsing** — 60 pages per minute per visitor.

If a legitimate user ever hits a limit (unusual), they see a friendly "try again in a moment" message. Nothing else breaks.

---

# 12. Technical Reference

> *Everything below is for developers and Platform Ops. Non-technical staff can skip this — nothing here is required for daily use.*

## 12.1 Full permission matrix

Full permission keys live in `backend/core/role_registry.py`. Changes to permissions require both a code change AND a migration to backfill legacy users.

## 12.2 Data model overview {#12-data-model}

Core entities (see `backend/models/` for the full list):

- **Organization** — tenant boundary
- **User** — with roles + cohort
- **Course** → **CourseSlide** (ordered) → **SlideComment**
- **Exam** → **ExamQuestion** → **ExamAttempt**
- **Flashcard** → **FlashcardReview** (SM-2 state per learner)
- **Enrolment** + **CourseProgress**
- **Certificate** + verifier token + revocation events
- **AITokenCall** + **AIJob** + **AIUsageLedger**
- **APIToken** + **APITokenCall**
- **WebhookSubscription** + **WebhookDelivery**
- **AuditLog** (append-only, 3-year retention)
- **Invitation** (with cohort binding)
- **OutboxMessage** (email queue)
- **BadgeTier** + **UserBadge**
- **LiveSession** + **LiveSessionRsvp**
- **CourseView** + **SlideView** (funnel analytics)

## 12.3 Backend Router Inventory

<!-- AUTO:BEGIN router_index -->
| File | Lines |
|---|---|
| `routers/admin_entitlements.py` | 185 |
| `routers/admin_organizations.py` | 202 |
| `routers/affiliate.py` | 263 |
| `routers/ai_tutor.py` | 386 |
| `routers/api_tokens.py` | 284 |
| `routers/auth.py` | 487 |
| `routers/authoring.py` | 131 |
| `routers/authoring_extras.py` | 198 |
| `routers/authoring_media.py` | 284 |
| `routers/authoring_tutor.py` | 458 |
| `routers/badge_tiers.py` | 133 |
| `routers/courses.py` | 836 |
| `routers/docs_library.py` | 103 |
| `routers/email_diagnostics.py` | 127 |
| `routers/erp360_sync.py` | 426 |
| `routers/exams.py` | 459 |
| `routers/extras.py` | 655 |
| `routers/feedback.py` | 72 |
| `routers/flashcards.py` | 497 |
| `routers/imports.py` | 502 |
| `routers/invitations.py` | 206 |
| `routers/iter5.py` | 352 |
| `routers/iter8.py` | 367 |
| `routers/learning_paths.py` | 285 |
| `routers/live_sessions.py` | 851 |
| `routers/marketplace_analytics.py` | 430 |
| `routers/misc.py` | 1391 |
| `routers/narration.py` | 204 |
| `routers/onboarding.py` | 97 |
| `routers/owner_dashboard.py` | 226 |
| `routers/public_catalog.py` | 201 |
| `routers/query_builder.py` | 250 |
| `routers/scheduled_reports.py` | 188 |
| `routers/scorm_xapi.py` | 512 |
| `routers/seo.py` | 369 |
| `routers/stripe_payments.py` | 303 |
| `routers/terms_kiosk.py` | 339 |
| `routers/totp.py` | 268 |
| `routers/webhooks.py` | 253 |
| **Total** | **13780** |
<!-- AUTO:END router_index -->

## 12.2 Model Inventory

<!-- AUTO:BEGIN model_index -->
| Model | Table |
|---|---|
| `AIJob` | `ai_jobs` |
| `AITutorMessage` | `ai_tutor_messages` |
| `AITutorSession` | `ai_tutor_sessions` |
| `AIUsageLedger` | `ai_usage_ledger` |
| `AccountDeletionRequest` | `account_deletion_requests` |
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
| `CourseRating` | `course_ratings` |
| `CourseSlide` | `course_slides` |
| `CourseView` | `course_views` |
| `CustomThemePreset` | `custom_theme_presets` |
| `EmailVerificationToken` | `email_verification_tokens` |
| `Enrollment` | `enrollments` |
| `Erp360SeenEvent` | `erp360_seen_events` |
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
| `PasswordResetToken` | `password_reset_tokens` |
| `PaymentTransaction` | `payment_transactions` |
| `Person` | `persons` |
| `ProgressOutbox` | `progress_outbox` |
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
| `TesterFeedback` | `tester_feedback` |
| `User` | `users` |
| `UserBadge` | `user_badges` |
| `UserRole` | `user_roles` |
| `WebhookDelivery` | `webhook_deliveries` |
| `WebhookSubscription` | `webhook_subscriptions` |
| `XApiStatement` | `xapi_statements` |

_Total: **63** ORM models._
<!-- AUTO:END model_index -->

---

# 13. API Reference (Selective) {#13-api}

Full OpenAPI at `/docs`. The full route table is regenerated automatically:

<!-- AUTO:BEGIN api_routes -->
| Endpoint | Verb | Purpose |
|---|---|---|
| `/api` | GET |  |
| `/api/academies` | GET | List all academies with optional search (name/slug), status filter, and sort. |
| `/api/academies` | POST |  |
| `/api/admin/affiliate/codes` | GET |  |
| `/api/admin/affiliate/codes` | POST |  |
| `/api/admin/affiliate/codes/{code_id}` | PATCH |  |
| `/api/admin/affiliate/earnings` | GET | Aggregate earnings by status. Cents-based to avoid float drift. |
| `/api/admin/affiliate/referrals` | GET | Referrals attributed to codes I own. |
| `/api/admin/affiliate/referrals/{referral_id}/mark-credited` | POST |  |
| `/api/admin/analytics` | GET |  |
| `/api/admin/analytics/enrollments-weekly` | GET | Enrolments or completions per ISO week (Iter 43/44 dashboard chart). |
| `/api/admin/api-tokens` | GET |  |
| `/api/admin/api-tokens` | POST |  |
| `/api/admin/api-tokens/analytics/spend` | GET | Per-day $ spend across all AI providers for the last `days` days. |
| `/api/admin/api-tokens/analytics/usage` | GET | Return per-day request counts for the org over the last `days` days, |
| `/api/admin/api-tokens/{token_id}` | DELETE |  |
| `/api/admin/api-tokens/{token_id}/revoke` | POST |  |
| `/api/admin/audit-digest` | GET | LLM-generated plain-English summary of the last N days of admin |
| `/api/admin/audit-log` | GET |  |
| `/api/admin/cert-preview` | POST | Render a SAMPLE certificate PDF using the supplied branding — no DB writes. |
| `/api/admin/cohorts` | GET | Distinct cohort labels with learner counts. |
| `/api/admin/course-dropoff/{course_id}` | GET | Iter 26 — Per-slide unique-viewers + drop-off %. For each slide |
| `/api/admin/dashboard/docs-engagement` | GET | Iter 33c — Docs engagement tile for the Owner dashboard. |
| `/api/admin/dashboard/members-needing-action` | GET |  |
| `/api/admin/docs` | GET | Return catalog of downloadable documents with metadata. |
| `/api/admin/docs/{slug}/pdf` | GET | Stream a rendered PDF of the requested document. |
| `/api/admin/docs/{slug}/raw` | GET | Return the raw markdown source (with AUTO-BLOCK markers). |
| `/api/admin/email/send-test` | POST | Queue a test email and dispatch it synchronously so the admin |
| `/api/admin/email/transport-status` | GET | Report which delivery transports are active for THIS org, in |
| `/api/admin/entitlements/user/{user_id}` | GET | List every paid course in the caller's org + whether the target |
| `/api/admin/entitlements/user/{user_id}/course/{course_id}` | GET | One user, one course — the "why can't they enroll?" answer. |
| `/api/admin/feature-flags/{flag_key}` | PUT |  |
| `/api/admin/feedback` | GET | All feedback for the caller's org, newest first. |
| `/api/admin/feedback/{feedback_id}/status` | POST | Flip a feedback item between NEW and REVIEWED. |
| `/api/admin/imports` | GET |  |
| `/api/admin/imports/run` | POST | Kick off a bulk import. Returns immediately with the new ImportJob row; |
| `/api/admin/imports/upload-zip` | POST | Drag-and-drop a content-tree ZIP. We extract it to a temp staging |
| `/api/admin/imports/{job_id}` | GET |  |
| `/api/admin/imports/{job_id}/rollback` | POST | Undo an import job — deletes every course / learning path it created. |
| `/api/admin/invitations` | GET |  |
| `/api/admin/invitations` | POST |  |
| `/api/admin/invitations/bulk` | POST | Issue up to 500 invitations in one call. Each row returns its own |
| `/api/admin/invitations/{invitation_id}` | DELETE |  |
| `/api/admin/kiosk/settings` | PUT |  |
| `/api/admin/leaderboard.csv` | GET |  |
| `/api/admin/marketplace-funnel` | GET | Iter 25 — Cross-course marketplace funnel roll-up for the current |
| `/api/admin/marketplace-funnel/{course_id}` | GET |  |
| `/api/admin/onboarding/checklist` | GET |  |
| `/api/admin/organizations` | GET | List every org in the deployment (super-admin only — regular |
| `/api/admin/organizations/{org_id}/integrations/erp360` | GET |  |
| `/api/admin/organizations/{org_id}/integrations/erp360` | PATCH | Merge-update the org's ERP360 integration config. Only the |
| `/api/admin/outbox` | GET |  |
| `/api/admin/outbox/stats` | GET |  |
| `/api/admin/outbox/{message_id}/retry` | POST | Reset a FAILED or DEAD_LETTER message back to QUEUED so the worker |
| `/api/admin/query-builder/build` | POST |  |
| `/api/admin/reports/cohort-stats` | GET | Completion / exam-score / time-to-graduation for a cohort, or for |
| `/api/admin/scheduled-reports` | GET |  |
| `/api/admin/scheduled-reports` | POST |  |
| `/api/admin/scheduled-reports/{report_id}` | DELETE |  |
| `/api/admin/scheduled-reports/{report_id}` | PUT |  |
| `/api/admin/scheduled-reports/{report_id}/run-now` | POST |  |
| `/api/admin/scorm` | GET |  |
| `/api/admin/scorm/upload` | POST | Upload a SCORM package. We extract it under SCORM_ROOT, parse the |
| `/api/admin/storage/info` | GET | Return the currently active storage backend + a probe result so admins |
| `/api/admin/terms` | GET |  |
| `/api/admin/terms` | POST |  |
| `/api/admin/terms/acceptances` | GET |  |
| `/api/admin/users` | GET |  |
| `/api/admin/users/{user_id}/2fa/disable` | POST |  |
| `/api/admin/webhooks` | GET |  |
| `/api/admin/webhooks` | POST |  |
| `/api/admin/webhooks/deliveries` | GET | Recent WebhookDelivery rows across ALL subscriptions in the |
| `/api/admin/webhooks/{sub_id}` | DELETE |  |
| `/api/admin/webhooks/{sub_id}` | PUT |  |
| `/api/admin/webhooks/{sub_id}/deliveries` | GET |  |
| `/api/admin/webhooks/{sub_id}/test` | POST | Fires a `webhook.test` event with a tiny payload so admins can confirm |
| `/api/affiliate/lookup/{code}` | GET | Public — thin preview so signup forms can show |
| `/api/ai/course-builder` | POST |  |
| `/api/auth/2fa/challenge` | POST | Public — accepts {challenge_id, code} and returns the standard |
| `/api/auth/2fa/disable` | POST |  |
| `/api/auth/2fa/setup` | POST |  |
| `/api/auth/2fa/setup-init` | POST | Return a fresh secret + QR. Nothing is persisted here — the |
| `/api/auth/2fa/status` | GET |  |
| `/api/auth/_test/reset-rate-limit` | POST |  |
| `/api/auth/change-password` | POST | Self-service password change. Verifies the old password, sets the |
| `/api/auth/forgot-password` | POST | Emails a single-use reset link if the address matches an active |
| `/api/auth/login` | POST |  |
| `/api/auth/logout` | POST |  |
| `/api/auth/me` | DELETE | Step 2 of self-deletion. Consumes the emailed code + anonymises |
| `/api/auth/me` | GET |  |
| `/api/auth/me/delete-request` | POST | Step 1 of self-deletion. Emails a 6-digit confirmation code that |
| `/api/auth/me/export` | GET | GDPR Right to Data Portability. Returns a JSON bundle of every |
| `/api/auth/refresh` | POST |  |
| `/api/auth/register` | POST |  |
| `/api/auth/resend-verification` | POST | Re-issue + email a verification link. Rate-limited (2/hr per |
| `/api/auth/reset-password` | POST | Consume a reset token + set a new password. On success, logs the |
| `/api/auth/sso-exchange` | POST | Inbound SSO from ERP360. Supports two response modes: |
| `/api/auth/sso-status` | GET | Public endpoint — the login page calls this on mount to decide whether |
| `/api/auth/verify-email` | POST | Consume an email-verification token. Called by the /verify-email/:token |
| `/api/authoring/budget` | GET |  |
| `/api/authoring/budget` | PUT |  |
| `/api/authoring/flashcards/bulk-save` | POST | Persist a reviewed batch. Overwrites nothing — creates fresh rows. |
| `/api/authoring/flashcards/by-course/{course_id}` | GET |  |
| `/api/authoring/flashcards/generate` | POST | Preview AI-generated flashcards. Does NOT persist — the client shows a |
| `/api/authoring/flashcards/{card_id}` | DELETE |  |
| `/api/authoring/flashcards/{card_id}` | PATCH |  |
| `/api/authoring/mindmap/{course_id}` | POST |  |
| `/api/authoring/mindmap/{course_id}/layout` | DELETE |  |
| `/api/authoring/mindmap/{course_id}/layout` | GET |  |
| `/api/authoring/mindmap/{course_id}/layout` | PUT |  |
| `/api/authoring/narration/generate` | POST |  |
| `/api/authoring/narration/languages` | GET | Static list of supported TTS languages — surfaced in the picker. |
| `/api/authoring/narration/{slide_id}` | DELETE |  |
| `/api/authoring/pptx/{course_id}` | GET |  |
| `/api/authoring/redaction/preview` | POST | Small utility endpoint: shows staff exactly what PII gets stripped |
| `/api/authoring/research` | GET | List recent research jobs for the org's history view. |
| `/api/authoring/research/start` | POST | Kick off a deep research job. Returns immediately with the AIJob id. |
| `/api/authoring/research/{job_id}` | GET |  |
| `/api/authoring/sources` | GET |  |
| `/api/authoring/sources` | POST | Upload a source. Two modes: |
| `/api/authoring/sources/search` | POST |  |
| `/api/authoring/sources/{doc_id}` | DELETE |  |
| `/api/authoring/status` | GET | Landing endpoint that the frontend hits when a staff user opens the |
| `/api/authoring/tutor/ask` | POST |  |
| `/api/authoring/video/generate` | POST | Kick off a Sora 2 job. Returns 202 with the AIJob id — poll |
| `/api/authoring/video/history` | GET |  |
| `/api/authoring/video/preview` | POST | Show the estimated cost + remaining budget BEFORE firing a Sora |
| `/api/authoring/video/{job_id}` | GET |  |
| `/api/authoring/visuals/generate` | POST | Generates a PNG infographic. If `slide_id + attach_to_slide` are set, |
| `/api/badge-tiers` | GET |  |
| `/api/badge-tiers` | POST |  |
| `/api/badge-tiers/reorder` | PATCH |  |
| `/api/badge-tiers/{tier_id}` | DELETE |  |
| `/api/badge-tiers/{tier_id}` | PATCH |  |
| `/api/billing/subscribe` | POST |  |
| `/api/billing/subscriptions` | GET |  |
| `/api/billing/webhook` | POST | Receives ERP360 billing webhooks. Verified via X-Signature header. |
| `/api/branding/public` | GET | Fetch org branding by slug (query param). If no slug is passed, we |
| `/api/catalog` | GET |  |
| `/api/catalog/organizations` | GET | Iter 27 — Cross-tenant marketplace search: list opted-in |
| `/api/catalog/{course_id}` | GET | Public course detail — shown on marketplace product page. |
| `/api/catalog/{course_id}/reviews` | GET | Best written reviews for a public course — highest stars first, |
| `/api/catalog/{course_id}/slides/{slide_id}/track-view` | POST | Iter 26 — Fire once per (slide, learner, day) from the course |
| `/api/catalog/{course_id}/track-view` | POST |  |
| `/api/certificates` | GET |  |
| `/api/certificates/admin-export.csv` | GET | Iter 30 — CSV export for compliance / auditors. All org certs |
| `/api/certificates/admin-list` | GET | Iter 30 — Admin view: paginated list of ALL certs in the org. |
| `/api/certificates/bulk-email` | POST | Iter 31 — Bulk re-email certificate download links to owners. |
| `/api/certificates/bulk-revoke` | POST | Iter 30 — Bulk revoke. Skips already-revoked certs (idempotent) |
| `/api/certificates/bulk-unrevoke` | POST | Iter 31 — Bulk lift-revocation. Skips currently-active certs |
| `/api/certificates/bulk-zip` | POST | Iter 31 — Bundle up to 100 cert PDFs into a single ZIP for |
| `/api/certificates/transcript` | GET | Generate a branded PDF transcript for the calling user. Lists every |
| `/api/certificates/transcript.json` | GET | Iter 50 — JSON payload behind the printable transcript page. |
| `/api/certificates/verify/{code}` | GET |  |
| `/api/certificates/verify/{code}/og-image.png` | GET | Iter 50 — PNG OG image for social share previews. LinkedIn does |
| `/api/certificates/verify/{code}/og-image.svg` | GET | Iter 28 — SVG OG image for social share previews. 1200×630 to |
| `/api/certificates/{cert_id}/pdf` | GET | Generate a branded PDF for a certificate. Owner or admin only. |
| `/api/certificates/{cert_id}/revocation-history` | GET | Iter 30 — Compliance audit trail. Lists REVOKE/UNREVOKE events |
| `/api/certificates/{cert_id}/revoke` | POST | Iter 29 — Revoke a certificate. Requires ADMIN role. Idempotent |
| `/api/certificates/{cert_id}/unrevoke` | POST | Iter 29 — Clear a revocation flag. In case of a mistaken |
| `/api/courses` | GET |  |
| `/api/courses` | POST |  |
| `/api/courses/reorder` | PATCH | Body: {"course_ids": [id1, id2, ...]} — sets display_order to the |
| `/api/courses/{course_id}` | DELETE |  |
| `/api/courses/{course_id}` | GET |  |
| `/api/courses/{course_id}` | PATCH |  |
| `/api/courses/{course_id}/complete` | POST |  |
| `/api/courses/{course_id}/duplicate` | POST | Deep-clone a course (with all slides) as a new DRAFT. Optional template path: |
| `/api/courses/{course_id}/enroll` | POST |  |
| `/api/courses/{course_id}/prerequisites` | GET |  |
| `/api/courses/{course_id}/prerequisites/{prereq_course_id}` | DELETE |  |
| `/api/courses/{course_id}/prerequisites/{prereq_course_id}` | POST |  |
| `/api/courses/{course_id}/publish` | POST | Explicit publish action with validation. Course must have at least |
| `/api/courses/{course_id}/rating` | GET | Average + count + the caller's own rating for a course. |
| `/api/courses/{course_id}/rating` | POST | Rate a course you have COMPLETED (1-5 stars, upsert). Iter 44. |
| `/api/courses/{course_id}/reviews` | GET | All written reviews for a course (incl. hidden) — admin moderation view. Iter 47. |
| `/api/courses/{course_id}/reviews/{rating_id}/reply` | POST | Post/update a public academy reply under a learner review. |
| `/api/courses/{course_id}/reviews/{rating_id}/toggle-hidden` | POST | Hide/unhide a written review from the public course page. Iter 47. |
| `/api/courses/{course_id}/slides` | POST |  |
| `/api/courses/{course_id}/slides/reorder` | PATCH | Reorder slides. Declared BEFORE /slides/{slide_id} to avoid path collision. |
| `/api/courses/{course_id}/slides/{slide_id}` | DELETE |  |
| `/api/courses/{course_id}/slides/{slide_id}` | PATCH |  |
| `/api/courses/{course_id}/slides/{slide_id}/versions` | GET |  |
| `/api/courses/{course_id}/slides/{slide_id}/versions/{version_number}` | GET |  |
| `/api/courses/{course_id}/slides/{slide_id}/versions/{version_number}/restore` | POST |  |
| `/api/courses/{course_id}/toggle-featured` | POST | Flip the marketplace 'Featured' flag on a course (Iter 42). |
| `/api/courses/{course_id}/unpublish` | POST |  |
| `/api/docs` | GET |  |
| `/api/enrollments` | GET |  |
| `/api/erp360/sync/status` | GET | Public probe. Returns whether IFPI is ready to receive ERP360 |
| `/api/erp360/sync/test-ping` | POST | Round-trip verification. Currently a stub — synthetic outbound |
| `/api/erp360/webhooks/user` | POST | Receive `user.role_changed` and `user.deactivated` events from ERP360. |
| `/api/exams` | GET |  |
| `/api/exams` | POST |  |
| `/api/exams/ai-generate-questions` | POST | Generate exam questions from a course's slide content using the |
| `/api/exams/{exam_id}` | DELETE |  |
| `/api/exams/{exam_id}` | GET |  |
| `/api/exams/{exam_id}` | PATCH |  |
| `/api/exams/{exam_id}/attempts` | GET | Per-learner attempt summary for an exam (admin/instructor). |
| `/api/exams/{exam_id}/attempts` | POST |  |
| `/api/exams/{exam_id}/attempts/reset` | POST | Wipe a learner's attempts for one exam so they can retake it. |
| `/api/exams/{exam_id}/question-insights` | GET | Per-question correct/miss rates across all attempts, so admins can |
| `/api/exams/{exam_id}/question-insights.csv` | GET | Same data as /question-insights, as a CSV for curriculum reviews. |
| `/api/exams/{exam_id}/questions` | PUT | mode='replace' (default) wipes & sets. mode='append' adds to existing. |
| `/api/exams/{exam_id}/questions/{question_id}` | PATCH | Edit one question in place — unlike PUT /questions (replace), this |
| `/api/feature-flags` | GET |  |
| `/api/feedback` | POST | Log an in-app feedback item (bug report, idea, other). |
| `/api/gamification/leaderboard` | GET |  |
| `/api/gamification/learning-streak` | GET | Iter 26 — Consecutive-day learning streak. A day counts when the |
| `/api/gamification/me` | GET |  |
| `/api/gamification/preferences` | GET | Iter 31 — per-user gamification preferences. |
| `/api/gamification/preferences` | PATCH | Iter 31 — toggle weekly streak digest opt-in/out. |
| `/api/gamification/streak-leaderboard` | GET | Iter 28 — Org-wide "top streaks this week" leaderboard. |
| `/api/health` | GET |  |
| `/api/invitations/{token}` | GET |  |
| `/api/invitations/{token}/accept` | POST |  |
| `/api/kiosk/settings` | GET |  |
| `/api/kiosk/unlock` | POST |  |
| `/api/leads` | POST | Public endpoint for partner sites / marketing pages to drop a lead in. |
| `/api/leads/embed.js` | GET | Self-contained JS widget that partner sites drop on their page. |
| `/api/learn/flashcards/courses/{course_id}/due` | GET | Return the learner's due-today queue for a course. Mixes: |
| `/api/learn/flashcards/courses/{course_id}/stats` | GET |  |
| `/api/learn/flashcards/streak` | GET | Learner's current + longest flashcard streak. Computed from |
| `/api/learn/flashcards/{card_id}/review` | POST |  |
| `/api/learning-paths` | GET |  |
| `/api/learning-paths` | POST |  |
| `/api/learning-paths/{path_id}` | DELETE |  |
| `/api/learning-paths/{path_id}` | GET |  |
| `/api/learning-paths/{path_id}` | PATCH |  |
| `/api/learning-paths/{path_id}/enroll` | POST |  |
| `/api/learning-paths/{path_id}/items` | POST |  |
| `/api/learning-paths/{path_id}/items/reorder` | PATCH | Accepts {"item_ids": [id1, id2, ...]}. |
| `/api/learning-paths/{path_id}/items/{course_id}` | DELETE |  |
| `/api/learning-paths/{path_id}/publish` | POST |  |
| `/api/live-sessions` | GET |  |
| `/api/live-sessions` | POST |  |
| `/api/live-sessions/subscribe-url` | POST | Return a URL the caller can hand to their calendar app. The URL |
| `/api/live-sessions/subscribe-url/qr` | GET | Iter 25 — Return an SVG QR code encoding the current user's |
| `/api/live-sessions/subscribe-url/rotate` | POST | Iter 25 — Bump the org's subscription_secret_version. Every |
| `/api/live-sessions/subscribe/{token}.ics` | GET | Iter 24 — Persistent calendar subscription. Token authenticates |
| `/api/live-sessions/upcoming` | GET | List sessions the current user can RSVP to: their cohort (or |
| `/api/live-sessions/{session_id}` | DELETE |  |
| `/api/live-sessions/{session_id}` | GET |  |
| `/api/live-sessions/{session_id}` | PATCH |  |
| `/api/live-sessions/{session_id}/cancel` | POST | Iter 24 — Cancel a single occurrence (RRULE EXDATE semantics). |
| `/api/live-sessions/{session_id}/ics` | GET |  |
| `/api/live-sessions/{session_id}/mark-attendance` | POST |  |
| `/api/live-sessions/{session_id}/rsvp` | POST | RSVP to a single session (default) OR the whole series when |
| `/api/live-sessions/{session_id}/uncancel` | POST |  |
| `/api/notifications` | GET |  |
| `/api/notifications/read-all` | PATCH |  |
| `/api/openapi.json` | GET |  |
| `/api/organization` | GET |  |
| `/api/organization` | PATCH |  |
| `/api/organization/apply-theme/{slug}` | POST | Copy a preset's branding values onto the caller's organization. |
| `/api/organization/cohort-digest/send-now` | POST | Manual trigger — queues the weekly cohort digest immediately for this |
| `/api/organization/cohort-settings` | PUT |  |
| `/api/organization/cohort-settings/test-webhook` | POST | Send a sample celebration message to verify the configured webhook. |
| `/api/organization/smtp` | GET | Returns the SMTP config minus the password. Password is write-only. |
| `/api/organization/smtp` | PUT |  |
| `/api/organization/smtp/test` | POST | Send a test email immediately (synchronous, NOT via the outbox). |
| `/api/organization/themes` | GET | Built-in presets + this org's custom presets (marked `custom: true`). |
| `/api/organization/themes` | POST | Create a custom theme preset for the caller's organization. |
| `/api/organization/themes/{preset_id}` | DELETE | Delete a custom theme preset. Orgs currently using it keep their |
| `/api/organization/themes/{preset_id}` | PUT | Update a custom theme preset (org-scoped). |
| `/api/payments/v1/checkout/session` | POST | Create a Stripe Checkout Session for the target course. |
| `/api/payments/v1/checkout/status/{session_id}` | GET | Poll Stripe for the payment status of a checkout session and |
| `/api/portal/{slug}` | GET | Public landing data for an academy. Powers /a/<slug> on the frontend. |
| `/api/public/catalog` | GET | List PUBLISHED courses in the caller's org. Read-only, no PII. |
| `/api/public/certificates/verify/{code}` | GET | Anonymous verification. Rate-limited to 30/min per IP (Redis |
| `/api/public/guides/{filename}` | GET | Anonymous download of the platform user-guide PDFs. |
| `/api/rich-text/sanitize` | POST | Server-side HTML sanitizer for the rich-text editor preview. |
| `/api/scorm/files/{package_id}/{rel_path:path}` | GET | Serve a file from an extracted SCORM package. Path-traversal safe. |
| `/api/scorm/runtime.js` | GET | Serve the IFPI SCORM runtime bridge as a static JS payload. |
| `/api/seo/certificates/share/{code}` | GET | Iter 28 — Public shareable brag-card for a certificate. |
| `/api/seo/courses/share/{course_id}` | GET | Iter 48 — Public shareable link for a marketplace course. |
| `/api/seo/robots.txt` | GET |  |
| `/api/seo/sitemap-{org_id}.xml` | GET |  |
| `/api/seo/sitemap.xml` | GET |  |
| `/api/slides/{slide_id}/comments` | GET |  |
| `/api/slides/{slide_id}/comments` | POST |  |
| `/api/slides/{slide_id}/comments/{comment_id}` | DELETE |  |
| `/api/terms/accept` | POST |  |
| `/api/terms/current` | GET |  |
| `/api/tutor/ask` | POST |  |
| `/api/tutor/save-as-flashcard` | POST |  |
| `/api/tutor/sessions` | GET |  |
| `/api/tutor/sessions/{session_id}` | GET |  |
| `/api/tutor/sessions/{session_id}/archive` | POST |  |
| `/api/uploads/bulk-media` | POST | Multi-file upload. Each file is independently stored. Failed files |
| `/api/uploads/cover-library` | GET | Curated course-cover photo gallery (Iter 43). Files are placed by |
| `/api/uploads/files/{path:path}` | GET | Serve a previously-uploaded file. ONLY meaningful for the `local` |
| `/api/uploads/image` | POST | Accepts logo / signature image. Delegates to the configured storage |
| `/api/uploads/media` | POST | Single-file upload for video/audio/PDF/image. If `course_id` is set, |
| `/api/webhook/stripe` | POST | Stripe webhook receiver. Idempotent — the poll path and the |
| `/api/xapi/statements` | GET |  |
| `/api/xapi/statements` | POST |  |

_Total: **297** registered API endpoints._
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

# 14. Security & Observability {#14-security}

**Shipped in Iterations 32–33.** All items below apply automatically to every tenant — no per-org config needed.

## 14.1 Security headers
Injected on every response by `core/middleware.py::SecurityHeadersMiddleware`:

- `Content-Security-Policy` — locked to self + integrated third-parties (Sentry, Tavily)
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: same-origin`
- `Permissions-Policy: camera=(), microphone=(self), geolocation=()`

## 14.2 Sentry + correlation IDs
- Backend + frontend both initialise `sentry-sdk`. Trace sample-rate `0.2` in prod.
- Every request receives an `X-Correlation-ID` (generated or forwarded). Frontend Axios interceptor echoes it back so stack traces link across tiers.
- Add a DSN via `SENTRY_DSN` (backend) and `REACT_APP_SENTRY_DSN` (frontend). No DSN = Sentry silently no-ops.

## 14.3 Rate limiting
See § 10.8 for the endpoint table. Redis-backed (`RATE_LIMIT_REDIS_URL`) with in-memory fallback for dev.

## 14.4 Audit log
Every mutating admin action + every sensitive read (cert download, doc preview, GDPR export) writes to the `audit_logs` table. Immutable, retained 3 years, viewable at `/dashboard/audit`. Export via `GET /api/admin/audit-log?format=csv`.

## 14.5 Deployment fail-closed check
`python backend/scripts/deploy_precheck.py` runs at container startup and refuses to boot if:
- `ENVIRONMENT` unset (assumed prod)
- Dev secrets present (`JWT_SECRET=changeme`, `SEED_ADMIN_PASSWORD=admin123`, …)
- Mongo config detected (IFPI is PostgreSQL-only)
- CORS wildcard in prod
- `STORAGE_BACKEND=local` in prod

## 14.6 Locked-out rescue tool
`python backend/scripts/reset_admin_password.py --email <owner>` prints a random 20-char password and re-sets `must_change_password=true`. Idempotent seed script guarantees no user's password is ever overwritten by a redeploy.

---

# 15. Documentation Library (in-app) {#15-docs-library}

**Where to find these manuals inside IFPI:**

> `Dashboard → Organization Settings → Documents` (ADMIN+ only).

The tab (see `frontend/src/pages/dashboard/OrganizationDocumentsTab.tsx`) lists every manual with:
- Live line count, size, last-modified timestamp
- **Inline preview** — click a row to render the PDF in an iframe below (no download friction)
- **Download PDF** — server-rendered from the source markdown via `xhtml2pdf`, cached 1 h
- **Download Markdown** — raw source for import into Notion / Confluence
- Every preview and download is written to the audit log so admins can measure engagement.

**Catalog served by `/api/admin/docs`:**

| Slug | Title | Audience |
|---|---|---|
| `setup-manual` | IFPI Setup Manual | Owner, Super Admin |
| `user-manual` | IFPI User Manual | All roles |
| `integration-matrix` | IFPI ↔ ERP360 Integration Matrix | Platform Ops, Owner |
| `assessment` | IFPI vs ERP360 Comparative Assessment | Owner, Platform Ops |

**Endpoints (all `requires_admin`):**
- `GET /api/admin/docs` — manifest
- `GET /api/admin/docs/{slug}/pdf?preview=true|false` — streamed PDF
- `GET /api/admin/docs/{slug}/raw` — raw markdown

Manuals stay in sync with the codebase: AUTO-BLOCK sections (route index, model index, role matrix) are regenerated by `python backend/scripts/build_docs.py`. Human-written prose outside those markers is preserved.

---

*Regenerate this manual whenever routers or models change: `python /app/backend/scripts/build_docs.py`.*
