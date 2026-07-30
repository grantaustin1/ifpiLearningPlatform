# IFPI Learning Platform — Administrator User Guide

**Version 2.0 · July 2026 — Complete first-time walkthrough**

This is a step-by-step manual for administrators and instructors. It assumes
no prior knowledge of the platform. Every instruction refers to the exact
button and menu names you will see on screen.

---

## 1. Before You Start — Key Concepts

| Term | What it means |
|---|---|
| **Academy / Organization** | Your own private tenant. Everything you create (courses, learners, certificates) belongs to your academy and is invisible to other academies. |
| **Admin** | Full control: authoring, learners, billing, settings. |
| **Instructor** | Authoring and learner management, no org-level settings. |
| **Learner** | A student. Self-registered accounts are always learners. |
| **Course** | A sequence of slides a learner plays through. |
| **Exam** | An assessment attached to a course. Passing it issues a certificate. |
| **Slide** | One page of course content (rich text, may include narration audio). |
| **Cohort** | A label you attach to a group of invited learners so you can track them together. |
| **Entitlement** | The record that says "this learner may access this course" (via payment, free enrolment or a comp role). |
| **PUBLISHED / DRAFT** | Learners only ever see PUBLISHED courses and exams. |

**The sidebar.** After logging in as admin you will see a left sidebar with
these entries (top to bottom): *Dashboard, Courses, Learning Paths, Exams,
Certificates, Cert. audit, Leaderboard, Badge tiers, Reports, Marketplace
analytics, Scheduled reports, Live sessions, Email diagnostics, Affiliate,
Query builder, Users, Email Outbox, Billing, Settings, Audit log, Webhooks,
Deliveries, ERP360, Entitlements, Content imports, Deep research, API tokens,
Academies, Public Catalog.* This guide walks through all of them.

---

## 2. Logging In for the First Time

1. Open the platform URL in Chrome, Edge, Firefox or Safari.
2. Enter the admin email and password you were given, and click **Sign in**.
3. **If you are redirected to a "Change password" screen:** this is normal —
   seeded admin accounts must set a fresh password on first login. Enter the
   old password, choose a new one, confirm it, and submit. You will land on
   the dashboard.
4. **If a 6-digit code is requested:** two-factor authentication is enabled
   for your account. Open your authenticator app (Google Authenticator,
   Authy, 1Password…) and type the current code.
5. **Forgot your password?** Click **Forgot password** on the login page,
   enter your email, and follow the reset link that is emailed to you.

> ⚠️ If a full-screen **Terms & Conditions** dialog appears, read and click
> **Accept** — you cannot use the platform until you do. (You control this
> gate yourself; see Section 18.3.)

---

## 3. Day-One Setup (do this once, ~15 minutes)

When you first open **Dashboard** you will see an **onboarding board** — a
checklist with a progress bar. Work through it in this order:

### 3.1 Brand your academy
1. Click **Settings** in the sidebar. You land on the **Branding &
   Certificates** tab (the other tabs are *Documents*, *Security*, *Terms &
   Kiosk*).
2. Set your **academy name** and **description** — these appear on your
   public catalog and in emails.
3. Upload your **logo** and pick your **primary colour**. The learner
   interface adopts this colour immediately.
4. Scroll to the certificate section and fill in:
   - **Accent colour** (defaults to your primary colour)
   - **Signature text** — e.g. "Jane Doe, Director of Education"
   - **Signature image** — an optional PNG/SVG of a real signature
   - **Footer text** — a disclaimer or contact line printed on every PDF
5. Click **Save**. Every certificate issued from now on uses this branding.

### 3.2 Connect outbound email (recommended, can be done later)
Without this, the platform still works but invitation/notification emails go
to a stub (they are logged, not delivered).

1. Click **Email diagnostics** in the sidebar.
2. The **transport status** panel shows which email route is active:
   per-tenant SMTP → system relay → bridge → stub.
3. To connect your own SMTP (e.g. SES, SendGrid, Mailgun, Office 365):
   go to **Settings → Branding & Certificates**, scroll to the SMTP section,
   and enter host, port, username, password, from-address. Save.
4. Back in **Email diagnostics**, type your own address in the **send test
   email** box and click send. You get an immediate result: SENT, STUB, or
   FAILED with the exact error.

> 💡 Until email is connected, you can always copy invitation links directly
> from the Users screen and send them by hand (Section 10.2).

### 3.3 Publish your Terms & Conditions (optional but recommended)
See Section 18.3. Learners are then required to accept them at login.

### 3.4 Create your first course, invite your first learner
Covered in full in Sections 5 and 10. The onboarding board ticks itself off
as you complete each item and disappears at 100%.

---

## 4. The Dashboard, Explained

- **Metric cards** — learners, active enrolments, completions, certificates.
- **Members Needing Action** — a live list of learners who are stalled,
  failing, or approaching a deadline. Each row shows the *reason*,
  colour-coded. Treat it as your to-do list; the same list is emailed to you
  in the Monday digest.
- **Docs engagement tile** — how much your document library is being read.
- **Onboarding board** — until you finish day-one setup.

---

## 5. Creating a Course Manually

### 5.1 Create the shell
1. Click **Courses** in the sidebar, then the **New Course** button
   (top-right).
2. Fill in:
   - **Title** and **description** (shown on the catalog card)
   - **Category** — free text, used for catalog filtering
   - **Duration (minutes)** — an estimate shown to learners
   - **Passing score** — e.g. 70 (%), used by the attached exam
   - **Price** — leave 0 for a free course (see Section 15 for pricing)
3. Save. The course is created in **DRAFT** status — invisible to learners.

### 5.2 Add and edit slides
1. Click the course to open the **course editor**. The left rail lists
   slides; the main pane edits the selected slide.
2. Click **Add slide**. Give it a **title** and write the **content** in the
   rich-text editor (headings, bold, lists, images).
3. Repeat for each slide. Drag slides in the left rail to reorder.
4. Click **Save** often (top-right). Every save creates a version snapshot.

### 5.3 Add voice narration (optional)
1. In the slide editor, open the **narration** panel.
2. Choose a **voice**, **model** and **language**. Tick **translate first**
   if the slide text is in a different language than the narration you want.
3. Click **Generate**. An audio player appears — listen, and regenerate or
   **clear** if you don't like it. Learners get a play button on the slide.

### 5.4 AI visuals for a slide (optional)
Open the **visual editor** on a slide, type a prompt describing the image
you want, generate, preview, and attach.

### 5.5 Prerequisites
In the editor's right rail, use **Add prerequisite** to require another
course to be completed first. Learners see the course locked until then.

### 5.6 Version history — undo anything
1. Click the **history** icon on a slide (or the version sidebar).
2. A list of dated versions appears. Select one to preview.
3. Click **Restore** and confirm. Nothing is ever lost — restoring also
   creates a new version.

### 5.7 Publish
Click **Publish** (top-right of the editor). The status pill changes from
DRAFT to **PUBLISHED** and the course appears in your catalog immediately.
**Unpublish** hides it again; enrolled learners keep their progress.

> 💡 You can also export any course as a PowerPoint file with the **PPTX
> download** button — useful for offline review.

---

## 6. Creating a Course with the AI Builder

1. Click **Courses → AI Builder** (next to New Course).
2. Describe what you want, for example: *"A 6-slide beginner course on
   client onboarding for new gym instructors, professional tone, with a
   short quiz."*
3. Click **Generate**. The AI drafts the full course: title, slides and
   content. This takes ~10–30 seconds.
4. Review the draft in the preview. If it's not right, adjust your prompt
   and regenerate.
5. Click **Apply** to create the course. It arrives in **DRAFT** status.
6. Open it in the course editor and treat it exactly like a manual course:
   edit any slide, add narration, reorder, then **Publish**.

> ⚠️ AI generation consumes your academy's monthly AI budget (default $200,
> adjustable). If generation fails with a budget message, see Section 20.

---

## 7. Exams & the AI Quiz Generator

### 7.1 Create an exam manually
1. Click **Exams → New Exam**.
2. Fill in: title, description, **linked course**, **time limit** (minutes),
   **passing score** (%), and **max attempts** per learner.
3. Add questions one at a time:
   - **Multiple choice** — enter the options and mark the correct one
   - **True/False**
   - Set **points** per question (defaults to 1).
4. Set the exam to **published** when ready. Learners see it at the end of
   the linked course.

### 7.2 Generate a quiz with AI
1. Click **Exams → AI Quiz**.
2. In the dialog choose:
   - the **course** whose slide content the questions should come from
   - the **number of questions**
   - the **question type** (multiple choice / true-false / mixed)
3. Click **Generate** and wait a few seconds. The questions appear for
   review — edit any wording, option or correct answer inline.
4. Choose the save mode:
   - **New exam** — creates a fresh exam for the course, or
   - **Append** — adds the questions to an existing exam you select.
5. Click **Save**. Review the final exam under **Exams** before publishing.

**How results work:** a learner's score is computed instantly on submission.
Passing triggers automatic certificate issuance (Section 13). Attempts are
counted against the max you set.

---

## 8. Flashcards & the Mind Map

### 8.1 Authoring flashcards
1. Open a course in the editor and click the **Flashcards** button, or use
   the flashcards authoring page.
2. Add cards manually (front/back), or generate them with AI from the course
   content. Delete any card with the bin icon (a confirmation dialog
   protects you).
3. Learners review the deck with a spaced-repetition scheduler — cards
   resurface just before they'd be forgotten.

### 8.2 The Mind Map
Click **Mind map** from the course editor for a visual canvas of your
courses and their relationships. Drag nodes to arrange; your layout is saved
automatically. **Clear layout** resets it.

---

## 9. The AI Knowledge Tools

### 9.1 Deep research (build your knowledge corpus)
1. Click **Deep research** in the sidebar.
2. Upload or paste source documents (policy PDFs, reports, articles). They
   are ingested into your academy's private corpus.
3. Ingested sources power semantic search, and the AI Tutor cites them when
   answering learners.

### 9.2 The AI Tutor (what your learners see)
Learners get an **Ask AI Tutor** button inside every course. Answers draw on
your course content and research corpus, with citations. Personal data in
learner questions is always redacted before AI processing — there is no way
to switch this off. You don't need to configure anything.

### 9.3 Query builder (ask your data questions)
1. Click **Query builder**.
2. Type a plain-English question, e.g. *"How many learners completed each
   course this month?"* — or click one of the sample questions.
3. The AI writes a **read-only** SQL query (shown to you, with a copy
   button) and runs it. Results appear as a table.
4. Guardrails: only SELECT queries, only over a safe set of tables, capped
   at 500 rows. It cannot modify anything.

---

## 10. Managing Learners

### 10.1 The Users screen
Click **Users**. You see everyone in your academy with role, cohort,
activity and streak. Self-registered accounts are always learners — admin
rights are granted by invitation only.

### 10.2 Invite one person
1. Click **Invite user**.
2. Enter **email**, **name**, and choose the **role** (Learner, Instructor
   or Admin).
3. Click **Send invite**. If email is connected, they receive a join link;
   if not, **copy the invite link** shown in the UI and send it yourself.
4. The invitee clicks the link, sets a password, and lands in your academy.

### 10.3 Invite a whole group (bulk / cohort)
1. Click **Bulk invite**.
2. Either upload a **CSV** or paste one email per line into the text box.
3. Choose the **role** for all of them and — important — type a **cohort**
   name (e.g. "Sept-2026-Intake"). The cohort tag follows these learners
   through analytics, digests and reports.
4. Click **Submit**. A per-row result list shows sent / already-exists /
   invalid for every address.

### 10.4 Cohort tracking
- **Reports → cohort progress** shows completion per cohort with CSV export.
- When a cohort crosses your completion threshold (default 75%, adjustable
  in Settings), a celebration fires — optionally to a Slack/Discord webhook.
- The **Monday digest email** recaps cohorts approaching or past target.

---

## 11. Learning Paths

1. Click **Learning Paths → New path**.
2. Name it and add courses in the order they must be completed
   (e.g. Foundation → Intermediate → Advanced).
3. Save and publish. Learners see the path with their position marked;
   finishing one step unlocks the next.
4. Edit or delete paths any time (delete asks for confirmation and does not
   delete the courses themselves).

---

## 12. Live Sessions

### 12.1 Create a session
1. Click **Live sessions → New session**.
2. Fill in: **title**, **date & time**, **meeting URL** (Zoom, Meet, Teams —
   any link), the **linked course**, and an optional capacity.
3. For a repeating session, set the **recurrence** (weekly/monthly) — you
   can exclude specific dates. Learners can RSVP per occurrence or for the
   whole series.
4. Save. The session appears to learners on the course page and in their
   sessions list, and reminder emails go out automatically beforehand.

### 12.2 RSVPs and auto-enrolment
Watch RSVPs arrive on each session card. If a learner RSVPs to a session for
a course they are not yet enrolled in, they are **auto-enrolled** — no extra
admin work.

### 12.3 Mark attendance
1. After the session, open it and click **Attendance**.
2. Tick attendees individually or use **bulk mark**.
3. Attendance certificates (if enabled for that session) are issued
   automatically and a confirmation email is sent to each attendee.

### 12.4 Calendar feeds
- Learners subscribe to a personal **ICS calendar URL** so sessions appear
  in Google/Apple/Outlook.
- If a subscription URL ever leaks, click **rotate secret** — every old
  calendar URL is invalidated instantly, without logging anyone out.

---

## 13. Certificates

### 13.1 How certificates are issued
Automatically — when a learner passes an exam, or attends a qualifying live
session. Every PDF carries your branding (Section 3.1) and a **QR code**
linking to a public verification page.

### 13.2 Verifying
Anyone can open the certificate's verify link (or scan the QR) and see
whether it is valid — no account needed. Employers use this.

### 13.3 Revoking a certificate
1. Click **Cert. audit** in the sidebar (the admin certificates screen).
2. Find the certificate — search by learner name, email or certificate
   code; filter by status or type.
3. Click **Revoke**, type the reason, confirm.
4. Effect: the public verify page immediately shows *invalid + reason*, the
   learner's PDF download is blocked, and the share page shows a REVOKED
   banner. LinkedIn/Twitter previews update on their next crawl.
5. Made a mistake? Click **Unrevoke** — access is restored instantly.

### 13.4 Bulk operations & audit
On the same screen you can select many certificates with the checkboxes and
**bulk revoke** them with one reason; download the full register as **CSV**
for auditors; and open the **revocation history** drawer on any certificate
to see who revoked/unrevoked it, when, and why.

---

## 14. Gamification

- **Badge tiers** — click **Badge tiers**, create tiers (name, points
  threshold, icon). Learners are promoted automatically as their XP grows.
  Deleting a tier asks for confirmation.
- **Leaderboard** — click **Leaderboard** to see the org ranking learners
  also see.
- **Streaks** — automatic. Learners keep a daily streak; the platform emails
  them a nudge when a streak is about to break, and emails *you* a weekly
  top-5 streak leaderboard digest.

---

## 15. Billing, Pricing & Payments

### 15.1 Price a course
Set the **price** field on the course (in cents — e.g. 49900 = R499.00).
Free courses (price 0) enrol instantly.

### 15.2 What learners experience
- **Free course** → Enrol button → instant access.
- **Priced course** → Enrol → secure checkout → access on payment
  confirmation → receipt on their **Subscriptions** page.

### 15.3 Test mode vs live
- In test/preview environments, the **Billing** page shows a stub banner and
  Stripe runs in **test mode**: card `4242 4242 4242 4242`, any future
  expiry, any CVC — no real money ever moves.
- In production, connect the live payment provider (Stripe, or the ERP360
  billing bridge for debit orders) — your platform operator configures this.

### 15.4 Entitlements — "why can/can't this learner access this course?"
Click **Entitlements** in the sidebar, look up the learner + course, and you
get the exact reason: paid, free enrolment, comp role, or nothing. Use this
before assuming a billing bug.

---

## 16. Marketing Tools

### 16.1 Public catalog & SEO
Your published courses are automatically listed on a public catalog page
(click **Public Catalog** in the sidebar to view yours) with search-engine
friendly URLs, a sitemap and social preview cards. No setup needed.

### 16.2 Marketplace
- Opt in under Settings (marketplace opt-in) to list your published courses
  in the **cross-academy marketplace**, discoverable by other academies'
  learners.
- Click **Marketplace analytics** to see views, clicks and conversions per
  course.

### 16.3 Affiliate / referral programme
1. Click **Affiliate**.
2. Click **Create code**: set the reward percentage and an internal note.
   An 8-character code is generated (no ambiguous characters).
3. Click **copy referral link** — it produces
   `https://<your-domain>/register?ref=CODE`. Give it to partners.
4. Sign-ups through that link are recorded as referrals. The earnings cards
   show **pending** vs **credited** totals; payouts are marked credited by
   a platform super-admin.
5. Toggle any code inactive at any time. Self-referrals are blocked
   automatically.

### 16.4 Certificate share cards
Every certificate has a branded share page with rich LinkedIn/Twitter
previews — every graduate becomes marketing. Nothing to configure.

---

## 17. Reports & Analytics

- **Reports** — enrolment, completion and certificate reports with CSV
  export; cohort CSV includes per-learner progress and badges.
- **Course funnel** (on the course page) — view → enrol → start → complete
  conversion for each course.
- **Slide drop-off** — inside course analytics; shows the exact slide where
  learners abandon. Use it to fix your weakest content.
- **Scheduled reports** — click **Scheduled reports → New**:
  1. choose the **report kind** — members needing action, cohort progress,
     certificate issuance, or enrolment summary;
  2. choose the **cadence** — daily, weekly, monthly;
  3. enter recipient emails; save.
  Use **Run now** on any row to email it immediately; **Pause** or
  **Delete** any time.
- **Query builder** — ad-hoc questions in plain English (Section 9.3).
- **Audit log** — click **Audit log** for a searchable trail of every
  significant admin action (who, what, when).

---

## 18. Settings Reference (all four tabs)

### 18.1 Branding & Certificates
Covered in Section 3.1 — plus SMTP settings, cohort celebration threshold
and webhook URL, digest toggles, marketplace opt-in, and the monthly AI
budget.

### 18.2 Security
- **Change password.**
- **Enable two-factor authentication (TOTP):** click enable → scan the QR
  code with your authenticator app → type the 6-digit code to confirm →
  **save the recovery codes** somewhere safe (each works once if you lose
  your phone).

### 18.3 Terms & Kiosk
- **Terms & Conditions:** paste your terms, click **Publish version**.
  Every user must accept before continuing; the acceptance ledger records
  who accepted which version, when, from which IP. Publishing a new version
  re-prompts everyone.
- **Kiosk mode** (for shared front-desk devices): enable it, set an unlock
  PIN. The screen locks after inactivity; staff unlock with the PIN or an
  admin password.
- **Feature flags:** switch individual platform features on/off for your
  academy (AI authoring, marketplace, live sessions, affiliate programme,
  API tokens, and more).

### 18.4 Documents
Upload reference documents for your team; the dashboard tile tracks
engagement.

---

## 19. Integrations (overview)

- **API tokens** — mint scoped, org-bound tokens so external systems can
  read your catalog through the public API. Revoke or delete any token;
  both ask for confirmation.
- **Webhooks** — register an HTTPS endpoint to receive signed events
  (enrolment completed, certificate issued/revoked, AI budget threshold…).
  **Deliveries** shows every attempt, its response code, and retries;
  failed deliveries are retried automatically then dead-lettered.
- **ERP360** — per-academy SSO and billing bridge for organizations that run
  ERP360. Configured by a super-admin under **ERP360**.
- **Content imports** — SCORM packages, xAPI content and bulk slide imports,
  each with one-click **rollback**.

---

## 20. Troubleshooting

| Problem | What to check, in order |
|---|---|
| Invitation email never arrived | 1) **Email diagnostics** → transport status (is it STUB?) 2) recipient spam folder 3) copy the invite link from **Users** and send manually |
| Learner says they can't see a course | 1) Course status is **PUBLISHED**? 2) **Entitlements** lookup for that learner+course 3) prerequisite course not completed? |
| Learner can't log in | 1) Correct academy URL? 2) **Forgot password** flow 3) account active in **Users**? |
| AI builder / quiz / tutor fails | 1) Academy monthly **AI budget** exhausted (Settings)? 2) platform AI key balance empty — contact your platform operator |
| Certificate verify page says invalid | Was it revoked? Open **Cert. audit** → revocation history |
| Webhook not arriving at your endpoint | **Deliveries** → inspect the attempt log; your endpoint must answer 2xx within a few seconds |
| Payment succeeded but no access | **Entitlements** lookup; webhooks are the source of truth — check the Outbox and payment provider dashboard |
| Emails stuck | **Email Outbox** → status column; re-queue failed items after fixing SMTP |

Still stuck? Note the page, the exact time, and what you clicked, and
contact your platform operator — the audit log and server logs make
timestamped reports fast to diagnose.

---

*IFPI Learning Platform — Administrator User Guide v2.0*
