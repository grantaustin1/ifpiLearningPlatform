# IFPI Learning Platform — Administrator User Guide

**Version 4.0 · August 2026 — Complete first-time walkthrough**

This is a step-by-step manual for administrators and instructors of the
International Fitness Professionals Institute learning platform. It assumes
no prior knowledge. Every instruction refers to the exact button and menu
names you will see on screen.

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
| **Exam gate** | When a course has a published exam, learners must finish every slide before the exam unlocks. |
| **Attempt** | One sitting of an exam. Each exam has a maximum attempt count you control — and you can reset a learner's attempts if they run out. |
| **Cohort** | A label you attach to a group of invited learners so you can track them together. |
| **Entitlement** | The record that says "this learner may access this course" (via payment, free enrolment or a comp role). |
| **Featured** | Courses you star appear first in the marketplace's Featured row and on the public landing page. |
| **PUBLISHED / DRAFT** | Learners only ever see PUBLISHED courses and exams. |

**The sidebar.** After logging in as admin you will see a left sidebar with:
*Dashboard, Courses, Learning Paths, Exams, Certificates, Cert. audit,
Leaderboard, Badge tiers, Reports, Marketplace analytics, Scheduled reports,
Live sessions, Email diagnostics, Affiliate, Query builder, Users, Email
Outbox, Feedback, Billing, Settings, Audit log, Webhooks, Deliveries, ERP360,
Entitlements, Content imports, Deep research, API tokens, Academies, Public
Catalog* — plus a **Help & guides** link at the bottom that opens this manual
as a PDF at any time.

---

## 2. Logging In for the First Time

1. Open the platform URL in Chrome, Edge, Firefox or Safari.
2. Enter the admin email and password you were given, and click **Sign in**.
3. **The Welcome Tour.** About a second after your first login, a short
   guided tour appears: a welcome card with a **Show me around** button.
   Click it to be walked through the six most important places (Dashboard,
   Courses, Exams & insights, the Feedback inbox, and the Report-an-issue
   button). Click **Skip tour** at any point to dismiss it. The tour shows
   **once per account** and never again.
4. **If you are redirected to a "Change password" screen:** this is normal —
   seeded admin accounts must set a fresh password on first login.
5. **If a 6-digit code is requested:** two-factor authentication is enabled
   for your account. Open your authenticator app and type the current code.
6. **Forgot your password?** Click **Forgot password** on the login page and
   follow the reset link that is emailed to you.

<img src="/app/docs/screenshots/guide/login.jpg" width="440">
<p class="fig">Figure 1 — The login page: email, password and the Forgot-password link.</p>

<img src="/app/docs/screenshots/guide/a_tour.jpg" width="440">
<p class="fig">Figure 2 — The one-time Welcome Tour spotlighting the sidebar on first login.</p>

> ⚠️ If a full-screen **Terms & Conditions** dialog appears, read and click
> **Accept** — you cannot use the platform until you do. (You control this
> gate yourself; see Section 19.3.)

---

## 3. Day-One Setup (do this once, ~15 minutes)

When you first open **Dashboard** you will see an **onboarding board** — a
checklist with a progress bar. Work through it in this order:

### 3.1 Brand your academy
1. Click **Settings**. You land on the **Branding & Certificates** tab.
2. Set your **academy name**, **description**, **logo** and **primary
   colour** — the learner interface adopts the colour immediately.
3. Fill in the certificate section: **accent colour**, **signature text**
   (e.g. "Jane Doe, Programme Director"), optional **signature image**, and
   **footer text**. Every certificate PDF inherits these.
4. Or pick a **Theme preset**: hover a preset card for **Preview** (renders a
   sample certificate without saving) and **Apply** (persists). You can also
   click **New preset** to save your own combination — custom presets get a
   "Custom" badge with **Edit** and **Delete** buttons.
5. Click **Save**.

### 3.2 Connect outbound email (recommended)
Without this the platform still works, but invitation/notification emails go
to a stub (logged, not delivered).

1. Click **Email diagnostics** — the transport panel shows which route is
   active: per-tenant SMTP → system relay → bridge → stub.
2. To connect your own SMTP, enter host/port/username/password/from-address
   in **Settings → Branding & Certificates** (SMTP section) and Save.
3. Back in **Email diagnostics**, use **send test email** — you get an
   immediate SENT / STUB / FAILED result with the exact error if any.

> 💡 Until email is connected you can always copy invitation links directly
> from the Users screen and send them by hand.

### 3.3 Publish your Terms & Conditions (optional)
See Section 19.3. Learners must then accept them at login.

### 3.4 Create your first course, invite your first learner
Covered in Sections 5 and 11. The onboarding board ticks itself off and
disappears at 100%.

---

## 4. The Dashboard, Explained

- **Metric cards** — learners, active enrolments, completions, certificates.
- **Members Needing Action** — learners who are stalled, failing, or
  approaching a deadline, with the reason colour-coded. Your Monday to-do
  list; also emailed in the weekly digest.
- **Weekly chart** — enrolments per week for the last 12 weeks. Use the
  toggle in its corner to switch between **Enrolments** and **Completions**;
  hover any bar for the exact count.
- **Recent Activity** — the latest enrolments as they happen.
- **Docs engagement tile** and the **onboarding board** (until complete).

<img src="/app/docs/screenshots/guide/a_dashboard.jpg" width="440">
<p class="fig">Figure 3 — The admin dashboard: metric cards, launch checklist and members needing action.</p>

---

## 5. Creating a Course Manually

### 5.1 Create the shell
1. Click **Courses → New Course**.
2. Fill in: **title**, **description**, **category**, **duration (minutes)**,
   **passing score** (e.g. 70), and **price** (0 = free).
3. Save. The course is created in **DRAFT** — invisible to learners.

<img src="/app/docs/screenshots/guide/a_courses.jpg" width="440">
<p class="fig">Figure 4 — The Courses screen: cover photos, status chips, star (feature) buttons.</p>

### 5.2 Add and edit slides
1. Open the course editor. The left rail lists slides; the main pane edits
   the selected slide.
2. Click **Add slide**, give it a title, write rich-text content. Repeat.
   Slides can also carry **video**, **image**, **audio**, **PDF** or
   **SCORM** media.
3. Drag slides in the left rail to reorder. Click **Save** often — every
   save creates a version snapshot.

<img src="/app/docs/screenshots/guide/a_course_edit.jpg" width="440">
<p class="fig">Figure 5 — The course editor: slide rail on the left, slide content in the middle, publishing and cover controls on the right.</p>

### 5.3 Give it a cover photo (recommended)
Courses look far better in the catalog with a real photo:

1. In the editor sidebar find the **Cover image** field.
2. Easiest: click **Gallery** — a curated grid of 15 professional fitness
   photos (weights rack, personal training, yoga, spin, nutrition coaching,
   boxing…) opens. Click one; it fills the field instantly.
3. Alternatively paste any **image URL**, or click **Upload** to use your own
   photo (max 5MB).
4. A live preview appears — remove it with the ✕ if you change your mind.
5. Click **Save**. The photo now shows on catalog cards, the landing page
   and your admin course grid.

### 5.4 Voice narration (optional)
Open the **narration** panel on a slide, choose a voice/model/language
(tick **translate first** if needed), click **Generate**, listen, keep or
regenerate. Learners get a play button on the slide.

### 5.5 Prerequisites, versions, publishing
- **Add prerequisite** (right rail) locks the course until another course is
  completed.
- The **history** icon lists dated version snapshots — select one and
  **Restore** to undo anything.
- Click **Publish** when ready; **Unpublish** hides it again without losing
  learner progress. **PPTX download** exports the course as PowerPoint.

### 5.6 Deleting a course permanently
On the **Courses** screen every course card has a small **bin button** next
to Duplicate. Deleting is deliberately strict:

1. **Unpublish first.** A published course cannot be deleted — the bin is
   greyed out and clicking it reminds you to open **Edit → Unpublish**.
   (Prefer Unpublish alone whenever you might want the course back: it hides
   the course without destroying anything.)
2. Click the **bin button** on the now-draft course. A confirmation dialog
   warns that deletion is **permanent**: all slides, flashcards, ratings and
   learner progress for the course are removed. Certificates already earned
   **stay valid**.
3. Click **Delete permanently** to confirm, or **Cancel**.

> ⚠️ Only the **course owner** (the account that created it) or a **super
> admin** can delete a course — other admins won't see the bin button on
> that card. Every deletion is recorded in the Audit log.

---

## 6. Creating a Course with the AI Builder

1. Click **Courses → AI Builder**.
2. Describe what you want, e.g. *"A 6-slide beginner course on client
   onboarding for new gym instructors, professional tone, with a short
   quiz."*
3. Click **Generate** (~10–30 seconds), review the draft, regenerate if
   needed, then **Apply**. The course arrives in DRAFT.
4. Edit it like any manual course — add a cover photo from the Gallery,
   tweak slides, then **Publish**.

> ⚠️ AI generation consumes your academy's monthly AI budget (default $200,
> adjustable in Settings). See Section 22 if generation fails.

---

## 7. Exams — Authoring, the Exam Gate & Attempts

### 7.1 Create an exam manually
**Exams → New Exam**: title, linked course, time limit, passing score, max
attempts. Add multiple-choice and true/false questions with points, then set
the exam to **published**.

<img src="/app/docs/screenshots/guide/a_exams.jpg" width="440">
<p class="fig">Figure 6 — The Exams screen: status, Attempts and Preview per exam, plus the AI quiz and New Exam buttons.</p>

### 7.2 Create an exam with AI
**Exams → AI Quiz**: pick the course, number of questions and question type;
**Generate**; edit any question inline; save as a **New exam** or **Append**
to an existing one.

### 7.3 What learners experience — the exam gate
When a course has a published exam, learners see an amber banner inside the
course player: *"This course ends with an exam — pass [exam name] to earn
your certificate."* The exam stays locked until **every slide is completed**;
on the final slide the button reads **Take exam** and leads straight into it.
Before starting, learners see the time limit, passing score and an
**Attempts left** counter. Passing issues the certificate automatically and
counts as a course completion (which learners can then rate — Section 10).

### 7.4 Reviewing attempts
On **Exams**, each exam card shows learner outcome chips (Passed / score /
No attempts). Click into an exam's attempts view — it has two tabs:

- **Learners** — every learner's attempts, scores, pass/fail and dates.
- **Question insights** — see Section 8.

<img src="/app/docs/screenshots/guide/a_attempts.jpg" width="440">
<p class="fig">Figure 7 — The Attempts view with its two tabs: Learners and Question insights.</p>

### 7.5 Resetting a learner's attempts
A learner who used every attempt is blocked from retrying — but you can give
them a fresh start:

1. Open the exam's **Learners** tab and find the learner.
2. Click **Reset attempts**. A confirmation dialog — *"Reset exam
   attempts?"* — explains exactly what will happen.
3. Confirm. All of that learner's attempts on this exam are cleared, their
   attempt counter returns to zero, and they are **notified by email**
   automatically that they may try again.
4. The reset is recorded in the **Audit log**.

> 💡 Certificates already earned are never removed by a reset — it only
> clears the attempt history so the learner can sit the exam again.

---

## 8. Exam Question Insights — Find What Learners Get Wrong

Open any exam and switch to the **Question insights** tab. This is your
question-quality dashboard, built from every submitted attempt:

### 8.1 Miss-rate bars
Each question row shows how many learners answered, how many got it right,
and a coloured **miss-rate bar**: red (50%+ missed), amber (25%+), green
(under 25%). Rows are sorted **most-missed first**, so the problem questions
are always at the top.

### 8.2 Distractor statistics
Expand a question to see the **answer distribution** — a bar per answer
option showing exactly how many learners picked it:

- the correct option is marked with a green ✓;
- the most-picked *wrong* option carries a red **TOP DISTRACTOR** badge.

If most learners pick the same wrong answer, the question wording (or your
course content) probably needs attention — that is exactly what this view is
for.

<img src="/app/docs/screenshots/guide/a_insights.jpg" width="440">
<p class="fig">Figure 8 — Question insights in action: miss-rate bars, per-option distributions, TOP DISTRACTOR badges, "author alerted" chips, Edit buttons and Export CSV.</p>

### 8.3 Miss-rate alerts (automatic)
You don't have to keep checking. When a question's miss rate reaches **50%
or more across at least 3 answers**, the platform automatically:

- sends an **in-app notification** and a **question miss alert email** to
  every instructor and admin in your academy;
- marks the question row with an **"author alerted"** chip so you can see at
  a glance which questions already fired.

Each question alerts **once** (no spam). When you edit the question the
alert **re-arms**, so if the fix didn't work you'll be told again.

### 8.4 Fixing a question without losing history
Click **Edit** on any insight row. The edit dialog lets you change the
question text, answer options, correct answer, points and explanation
**in place** — the question keeps its identity, so past attempts and the
statistics history stay linked. There's also an **Edit course content** link
in the insights header that jumps straight to the course editor if the
problem is the teaching material rather than the question.

### 8.5 Export the insights as CSV
Click **Export CSV** in the insights header to download the full table
(question, answered/correct/missed counts, miss rate, per-option
distribution) — ready for a spreadsheet or your quality-assurance file.

---

## 9. Flashcards, Mind Map & AI Knowledge Tools

- **Flashcards** — author cards manually or generate with AI; learners
  review them on a spaced-repetition schedule.
- **Mind map** — a drag-to-arrange visual canvas of your courses; layout is
  saved per user.
- **Deep research** — ingest source documents into your academy's private
  corpus; powers semantic search and AI Tutor citations.
- **AI Tutor** (learner-facing) — answers learner questions from your
  content with citations. Personal data in questions is always redacted
  before AI processing. Nothing to configure.
- **Query builder** — ask plain-English questions about your data ("how many
  learners completed each course this month?"); the AI writes a read-only
  SQL query and shows the results. SELECT-only, capped at 500 rows.

---

## 10. Marketplace Presence: Featured Courses & Ratings

### 10.1 Star your best courses
On **Courses**, every card has a small **star button** (top-left of the
cover). Click it to add the course to the **Featured row** of the public
marketplace — starred courses appear first (the row is topped up with your
most-enrolled courses so it never looks empty). Featured courses with photos
also appear on the public landing page. Click the star again to remove.

### 10.2 Course ratings
When learners finish a course they are invited to rate it 1–5 stars on the
completion screen. Average ratings appear as an amber star badge on catalog
cards — social proof that builds trust with new visitors. Ratings are only
possible after completion, and each learner's latest rating counts once.

---

## 11. The Feedback Inbox — Notes *and* Screenshots

Every logged-in user (admins and learners alike) has a floating
**Report an issue** button in the bottom-right corner. They pick 🐞 Bug /
💡 Idea / 💬 Other, type a message, and can now **attach a screenshot** —
either by choosing an image file or simply pasting one from the clipboard.
The page they were on is captured automatically.

You review submissions under **Feedback** in the sidebar:

- newest first, with the sender's name/email, page and timestamp;
- items with a screenshot show a **thumbnail** — click it to open the
  full-size image in a new tab;
- click **Mark reviewed** to tick items off (or **Reopen** to undo);
- feedback is private to your academy.

This is the fastest way to run UAT or collect learner suggestions without
leaving the platform: your testers' notes and screenshots all collect in one
place.

<img src="/app/docs/screenshots/guide/a_feedback.jpg" width="440">
<p class="fig">Figure 9 — The Feedback inbox: category chips, sender details and a clickable screenshot thumbnail.</p>

---

## 12. Managing Learners

### 12.1 Users
**Users** lists everyone with role, cohort, activity and streak.
Self-registered accounts are always learners; admin elevation is invite-only.

<img src="/app/docs/screenshots/guide/a_users.jpg" width="440">
<p class="fig">Figure 10 — The Users screen: roles, cohorts, activity and the invite buttons.</p>

### 12.2 Invite one person
**Users → Invite user**: email, name, role → **Send invite**. If email is
stubbed, copy the invite link from the UI and send it yourself.

### 12.3 Invite a whole group (bulk / cohort)
**Bulk invite**: upload a CSV or paste one email per line, choose the role,
and type a **cohort** name (e.g. "Sept-2026-Intake"). A per-row result shows
sent / already-exists / invalid.

### 12.4 Cohort tracking
**Reports → cohort progress** (CSV export included). Crossing your
completion threshold (default 75%) fires a celebration — optionally to a
Slack/Discord webhook — and features in the Monday digest.

---

## 13. Learning Paths

**Learning Paths → New path**: name it, add courses in order (Foundation →
Intermediate → Advanced). Learners see their position; finishing one step
unlocks the next.

---

## 14. Live Sessions

- **New session**: title, date/time, meeting URL (any provider), linked
  course, optional capacity, optional weekly/monthly **recurrence** with
  exception dates.
- **RSVPs**: learners RSVP per occurrence or whole series; RSVPing to a
  session of a course they aren't enrolled in **auto-enrols** them.
- **Attendance**: open the session → **Attendance** → tick attendees (bulk
  mark supported). Attendance certificates and confirmation emails are
  automatic.
- **Calendar feeds**: learners subscribe via a personal ICS URL; **rotate
  secret** org-wide if a link leaks. Reminder emails go out automatically.

---

## 15. Certificates & Transcripts

- **Issued automatically** on exam pass or qualifying attendance, branded
  per Section 3.1, with a QR code linking to public verification.
- **Verify**: anyone with the link/QR can confirm authenticity — no account
  needed.
- **Share cards**: every certificate has a branded public share page with a
  generated **preview image**, so pasting the link into LinkedIn, Twitter or
  WhatsApp shows a rich card with the learner's name and course — free
  marketing for your academy.
- **Revoke** (Cert. audit): find the certificate, click **Revoke**, give a
  reason. The verify page shows invalid+reason, the PDF download is blocked,
  and the share page shows a REVOKED banner. **Unrevoke** restores it.
- **Bulk operations**: multi-select bulk revoke, per-certificate revocation
  history drawer, and CSV export for auditors.
- **Learner transcripts**: every learner can download their own **academic
  transcript PDF** (all courses, progress, exam results and certificates)
  from **My Certificates → Download PDF**, or print the on-screen version
  via **Printable transcript**. Useful when learners need proof of study for
  an employer — no admin action required.

---

## 16. Gamification

- **Badge tiers** — create your own tiers (name, points threshold, icon);
  learners are promoted automatically.
- **Leaderboard** — the org ranking learners also see.
- **Streaks** — automatic daily streaks with "about to break" nudge emails
  to learners and a weekly top-5 digest to staff.

---

## 17. Billing, Pricing & Payments

- **Price a course** in the editor (cents — 49900 = R499.00). Free courses
  enrol instantly; priced courses route through checkout.
- **Test vs live**: test environments show a stub banner and run Stripe in
  test mode (card 4242 4242 4242 4242 — no real charges). Production
  connects live Stripe or the ERP360 billing bridge (debit orders).
- **Entitlements**: access is governed by the entitlement layer, not the
  payment provider. The **Entitlements** inspector shows exactly why a
  learner does or doesn't have access — check it before assuming a bug.

---

## 18. Marketing Tools

- **Public catalog & landing page** — published courses are listed publicly
  with SEO-friendly URLs, sitemap, social preview cards, cover photos,
  ratings, and the Featured strip. No setup needed.
- **Marketplace** — opt in (Settings) to be discoverable by other academies'
  learners; **Marketplace analytics** shows views/clicks/conversions.
- **Affiliate** — create referral codes (reward %, notes), copy the link
  (`/register?ref=CODE`), track pending vs credited earnings. Self-referrals
  are blocked.
- **Share cards** — certificates and courses both have share pages with rich
  social previews (Section 15).

---

## 19. Reports & Analytics

- **Reports** — enrolment/completion/certificate reports with CSV export.
- **Course funnel** and **slide drop-off** — find exactly where learners
  convert or abandon.
- **Exam question insights** — per-question miss rates, distractor stats and
  CSV export (Section 8).
- **Scheduled reports** — subscribe recipients to daily/weekly/monthly
  emails of four report kinds; **Run now** for an immediate send.
- **Dashboard weekly chart** — Enrolments/Completions toggle (Section 4).
- **Query builder** — ad-hoc questions (Section 9).
- **Audit log** — searchable trail of every significant admin action
  (including question edits and attempt resets).

<img src="/app/docs/screenshots/guide/a_reports.jpg" width="440">
<p class="fig">Figure 11 — Reports: enrolment/completion analytics with CSV export.</p>

---

## 20. Settings Reference

### 20.1 Branding & Certificates
Branding, certificate identity, theme presets (built-in + your own custom
ones), SMTP, cohort celebration threshold/webhook, digest toggles,
marketplace opt-in, monthly AI budget.

<img src="/app/docs/screenshots/guide/a_settings.jpg" width="440">
<p class="fig">Figure 12 — Settings → Branding &amp; Certificates: academy identity, certificate theme and SMTP.</p>

### 20.2 Security
Change password; enable TOTP two-factor (scan QR → confirm code → **save
the recovery codes**).

### 20.3 Terms & Kiosk
Publish versioned T&Cs (acceptance ledger records who/when/IP; a new version
re-prompts everyone). **Kiosk mode** locks shared devices after inactivity
with PIN unlock. **Feature flags** switch individual platform features
on/off for your academy.

### 20.4 Documents
Upload reference documents; the dashboard tile tracks engagement.

---

## 21. Integrations

- **API tokens** — scoped, org-bound tokens for external systems.
- **Webhooks** — HMAC-signed events (enrolment completed, certificate
  issued/revoked, AI budget threshold…); **Deliveries** shows every attempt
  and retry.
- **ERP360** — per-academy SSO and billing bridge (super admin).
- **Content imports** — SCORM/xAPI/bulk imports with one-click rollback.

---

## 22. Troubleshooting

| Problem | What to check, in order |
|---|---|
| Invitation email never arrived | 1) Email diagnostics → transport (STUB?) 2) spam folder 3) copy the invite link from Users |
| Learner can't see a course | 1) PUBLISHED? 2) Entitlements lookup 3) prerequisite incomplete? |
| Can't delete a course / no bin button | 1) Unpublish it first (Edit → Unpublish) 2) only the course owner or a super admin sees the bin button |
| Learner can't start the exam | The exam gate: every slide must be completed first — check their progress in Reports |
| Learner ran out of exam attempts | Exams → open the exam → Learners tab → **Reset attempts** (they're emailed automatically) |
| Learner can't log in | 1) correct URL? 2) Forgot password 3) account active in Users? |
| "Question miss alert" email — what is it? | A question is being missed by 50%+ of learners. Open Exams → Question insights, review the distractor stats, and edit the question or course content |
| AI builder / quiz / tutor fails | 1) monthly AI budget exhausted? 2) platform AI key balance — contact your operator |
| Certificate verify says invalid | revoked? Cert. audit → revocation history |
| Webhook not arriving | Deliveries → attempt log; endpoint must answer 2xx fast |
| Payment succeeded but no access | Entitlements lookup; check Outbox + provider dashboard |
| Rating button missing for a learner | ratings unlock only after full course completion |
| No feedback appearing | check the Feedback page — items are org-scoped; the widget is bottom-right on every logged-in page |
| Feedback screenshot won't upload | images only (PNG/JPG/WebP), max 5MB |
| The welcome tour won't show again | it runs once per account by design — it can be re-triggered by clearing the browser's site data |

Still stuck? Note the page, exact time and what you clicked — or ask the
user to send it via the **Report an issue** button (with a screenshot!) —
then contact your platform operator.

---

*IFPI Learning Platform — Administrator User Guide v4.0*
