# IFPI Learning Platform — Administrator User Guide

**Version 3.0 · July 2026 — Complete first-time walkthrough**

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
3. **If you are redirected to a "Change password" screen:** this is normal —
   seeded admin accounts must set a fresh password on first login.
4. **If a 6-digit code is requested:** two-factor authentication is enabled
   for your account. Open your authenticator app and type the current code.
5. **Forgot your password?** Click **Forgot password** on the login page and
   follow the reset link that is emailed to you.

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

---

## 5. Creating a Course Manually

### 5.1 Create the shell
1. Click **Courses → New Course**.
2. Fill in: **title**, **description**, **category**, **duration (minutes)**,
   **passing score** (e.g. 70), and **price** (0 = free).
3. Save. The course is created in **DRAFT** — invisible to learners.

### 5.2 Add and edit slides
1. Open the course editor. The left rail lists slides; the main pane edits
   the selected slide.
2. Click **Add slide**, give it a title, write rich-text content. Repeat.
3. Drag slides in the left rail to reorder. Click **Save** often — every
   save creates a version snapshot.

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
> adjustable in Settings). See Section 21 if generation fails.

---

## 7. Exams & the AI Quiz Generator

### 7.1 Manually
**Exams → New Exam**: title, linked course, time limit, passing score, max
attempts. Add multiple-choice and true/false questions with points, then set
the exam to **published**.

### 7.2 With AI
**Exams → AI Quiz**: pick the course, number of questions and question type;
**Generate**; edit any question inline; save as a **New exam** or **Append**
to an existing one.

Passing an exam issues the certificate automatically and counts as a course
completion (which learners can then rate — Section 10).

---

## 8. Flashcards, Mind Map & AI Knowledge Tools

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

## 9. Marketplace Presence: Featured Courses & Ratings

### 9.1 Star your best courses
On **Courses**, every card has a small **star button** (top-left of the
cover). Click it to add the course to the **Featured row** of the public
marketplace — starred courses appear first (the row is topped up with your
most-enrolled courses so it never looks empty). Featured courses with photos
also appear on the public landing page. Click the star again to remove.

### 9.2 Course ratings
When learners finish a course they are invited to rate it 1–5 stars on the
completion screen. Average ratings appear as an amber star badge on catalog
cards — social proof that builds trust with new visitors. Ratings are only
possible after completion, and each learner's latest rating counts once.

---

## 10. The Feedback Inbox

Every logged-in user (admins and learners alike) has a floating **feedback
button** in the bottom-right corner. They pick 🐞 Bug / 💡 Idea / 💬 Other,
type a message, and send — the page they were on is captured automatically.

You review submissions under **Feedback** in the sidebar:
- newest first, with the sender's name/email, page and timestamp
- click **Mark reviewed** to tick items off (or **Reopen** to undo)
- feedback is private to your academy.

This is the fastest way to run UAT or collect learner suggestions without
leaving the platform.

---

## 11. Managing Learners

### 11.1 Users
**Users** lists everyone with role, cohort, activity and streak.
Self-registered accounts are always learners; admin elevation is invite-only.

### 11.2 Invite one person
**Users → Invite user**: email, name, role → **Send invite**. If email is
stubbed, copy the invite link from the UI and send it yourself.

### 11.3 Invite a whole group (bulk / cohort)
**Bulk invite**: upload a CSV or paste one email per line, choose the role,
and type a **cohort** name (e.g. "Sept-2026-Intake"). A per-row result shows
sent / already-exists / invalid.

### 11.4 Cohort tracking
**Reports → cohort progress** (CSV export included). Crossing your
completion threshold (default 75%) fires a celebration — optionally to a
Slack/Discord webhook — and features in the Monday digest.

---

## 12. Learning Paths

**Learning Paths → New path**: name it, add courses in order (Foundation →
Intermediate → Advanced). Learners see their position; finishing one step
unlocks the next.

---

## 13. Live Sessions

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

## 14. Certificates

- **Issued automatically** on exam pass or qualifying attendance, branded
  per Section 3.1, with a QR code linking to public verification.
- **Verify**: anyone with the link/QR can confirm authenticity — no account.
- **Revoke** (Cert. audit): find the certificate, click **Revoke**, give a
  reason. The verify page shows invalid+reason, the PDF download is blocked,
  and the share page shows a REVOKED banner. **Unrevoke** restores it.
- **Bulk operations**: multi-select bulk revoke, per-certificate revocation
  history drawer, and CSV export for auditors.

---

## 15. Gamification

- **Badge tiers** — create your own tiers (name, points threshold, icon);
  learners are promoted automatically.
- **Leaderboard** — the org ranking learners also see.
- **Streaks** — automatic daily streaks with "about to break" nudge emails
  to learners and a weekly top-5 digest to staff.

---

## 16. Billing, Pricing & Payments

- **Price a course** in the editor (cents — 49900 = R499.00). Free courses
  enrol instantly; priced courses route through checkout.
- **Test vs live**: test environments show a stub banner and run Stripe in
  test mode (card 4242 4242 4242 4242 — no real charges). Production
  connects live Stripe or the ERP360 billing bridge (debit orders).
- **Entitlements**: access is governed by the entitlement layer, not the
  payment provider. The **Entitlements** inspector shows exactly why a
  learner does or doesn't have access — check it before assuming a bug.

---

## 17. Marketing Tools

- **Public catalog & landing page** — published courses are listed publicly
  with SEO-friendly URLs, sitemap, social preview cards, cover photos,
  ratings, and the Featured strip. No setup needed.
- **Marketplace** — opt in (Settings) to be discoverable by other academies'
  learners; **Marketplace analytics** shows views/clicks/conversions.
- **Affiliate** — create referral codes (reward %, notes), copy the link
  (`/register?ref=CODE`), track pending vs credited earnings. Self-referrals
  are blocked.
- **Share cards** — every certificate has a branded share page with rich
  LinkedIn/Twitter previews.

---

## 18. Reports & Analytics

- **Reports** — enrolment/completion/certificate reports with CSV export.
- **Course funnel** and **slide drop-off** — find exactly where learners
  convert or abandon.
- **Scheduled reports** — subscribe recipients to daily/weekly/monthly
  emails of four report kinds; **Run now** for an immediate send.
- **Dashboard weekly chart** — Enrolments/Completions toggle (Section 4).
- **Query builder** — ad-hoc questions (Section 8).
- **Audit log** — searchable trail of every significant admin action.

---

## 19. Settings Reference

### 19.1 Branding & Certificates
Branding, certificate identity, theme presets (built-in + your own custom
ones), SMTP, cohort celebration threshold/webhook, digest toggles,
marketplace opt-in, monthly AI budget.

### 19.2 Security
Change password; enable TOTP two-factor (scan QR → confirm code → **save
the recovery codes**).

### 19.3 Terms & Kiosk
Publish versioned T&Cs (acceptance ledger records who/when/IP; a new version
re-prompts everyone). **Kiosk mode** locks shared devices after inactivity
with PIN unlock. **Feature flags** switch individual platform features
on/off for your academy.

### 19.4 Documents
Upload reference documents; the dashboard tile tracks engagement.

---

## 20. Integrations

- **API tokens** — scoped, org-bound tokens for external systems.
- **Webhooks** — HMAC-signed events (enrolment completed, certificate
  issued/revoked, AI budget threshold…); **Deliveries** shows every attempt
  and retry.
- **ERP360** — per-academy SSO and billing bridge (super admin).
- **Content imports** — SCORM/xAPI/bulk imports with one-click rollback.

---

## 21. Troubleshooting

| Problem | What to check, in order |
|---|---|
| Invitation email never arrived | 1) Email diagnostics → transport (STUB?) 2) spam folder 3) copy the invite link from Users |
| Learner can't see a course | 1) PUBLISHED? 2) Entitlements lookup 3) prerequisite incomplete? |
| Learner can't log in | 1) correct URL? 2) Forgot password 3) account active in Users? |
| AI builder / quiz / tutor fails | 1) monthly AI budget exhausted? 2) platform AI key balance — contact your operator |
| Certificate verify says invalid | revoked? Cert. audit → revocation history |
| Webhook not arriving | Deliveries → attempt log; endpoint must answer 2xx fast |
| Payment succeeded but no access | Entitlements lookup; check Outbox + provider dashboard |
| Rating button missing for a learner | ratings unlock only after full course completion |
| No feedback appearing | check the Feedback page — items are org-scoped; the widget is bottom-right on every logged-in page |

Still stuck? Note the page, exact time and what you clicked — or ask the
user to send it via the **feedback widget** — then contact your platform
operator.

---

*IFPI Learning Platform — Administrator User Guide v3.0*
