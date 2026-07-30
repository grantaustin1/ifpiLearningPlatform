# IFPI Learning Platform — Administrator User Guide

**Version 1.0 · July 2026**

This guide covers everything an Organization Admin or Instructor needs to run
the IFPI Learning Platform: authoring courses (manually and with AI),
managing students, billing and pricing, marketing tools, live sessions,
analytics, and platform settings.

---

## 1. Getting Started

### 1.1 Logging in
Open the platform URL and sign in with your admin email and password. If your
account was just created you may be asked to set a new password on first
login. Two-factor authentication (TOTP) can be enabled later under
**Settings → Security**.

### 1.2 The Onboarding Board
On your first visit, the dashboard shows a 7-step onboarding checklist with a
progress bar:

1. Set your organization colour and logo
2. Create your first course
3. Invite your first learner
4. Configure the certificate signature
5. Connect SMTP for outbound email (optional)
6. Publish your Terms & Conditions
7. First learner activity

Each step has a shortcut button. The board disappears automatically once you
reach 100%.

### 1.3 Branding your academy
Go to **Settings → Organization**:

- **Name, description and logo** — shown on the login page, catalog and emails.
- **Primary colour** — applied across the learner UI.
- **Certificate branding** — accent colour, signature text (e.g. "Jane Doe,
  Director of Education"), signature image, and footer/disclaimer text. Every
  certificate PDF issued inherits these automatically.

---

## 2. The Admin Dashboard

The dashboard is your daily control room:

- **Key metrics** — learners, enrolments, completions, certificates issued.
- **Members Needing Action** — learners who are stalled, past-due on a
  cohort target, or approaching a deadline, with the reason colour-coded.
- **Engagement tiles** — document/library engagement and recent activity.
- **Onboarding board** (until complete).

The left sidebar gives access to every admin area described below.

---

## 3. Courses

### 3.1 Creating a course manually
**Courses → New Course**. Set the title, description, category, estimated
duration, passing score, and price (leave 0 for free). Then open the course
editor to add content:

- **Slides** — rich text (headings, lists, images), reorder by drag,
  multiple slide types.
- **Narration** — optional text-to-speech narration per slide; you can clear
  or regenerate it at any time.
- **Cover colour / imagery** — for the catalog card.

### 3.2 Versioning
Every significant edit creates a version snapshot. The version sidebar in the
course editor lets you inspect and **restore** any previous version — a
confirmation dialog protects you from accidental rollbacks.

### 3.3 Publishing
A course is invisible to learners until its status is **PUBLISHED**. You can
unpublish at any time; existing enrolments keep their progress.

### 3.4 The Mind Map
**Mind Map** gives a visual overview of your courses and learning paths.
Drag nodes to arrange them; the layout is saved per user and can be cleared.

### 3.5 Bulk imports (SCORM / xAPI / bulk content)
**Imports** accepts SCORM packages, xAPI content, and bulk slide imports.
Each import can be **rolled back** in one click if the result is not what you
expected. xAPI statements from imported content automatically drive
completion tracking.

---

## 4. The AI Authoring Suite

All AI features draw on your organization's monthly AI budget (configurable;
spend alerts fire via webhooks).

### 4.1 AI Course Builder
From **Courses**, use the AI builder: describe the topic, audience and depth,
and the AI drafts a complete course — slides, structure and a quiz. Review,
edit and publish. Everything the AI produces is fully editable afterwards.

### 4.2 AI Quiz Generator
Inside a course, generate quiz questions from the slide content. Questions
land in the exam editor where you can adjust wording, options, correct
answers and points before publishing.

### 4.3 Flashcards
**Flashcards** lets you author spaced-repetition flashcards per course, or
generate them with AI. Learners review them with an SM-2 scheduler.

### 4.4 Deep Research
**Research** ingests source documents into your organization's knowledge
corpus. Ingested sources power semantic search, AI tutor citations and
research-assisted authoring.

### 4.5 AI Tutor (learner-facing)
Learners get an "Ask AI Tutor" panel inside every course. Answers cite your
ingested sources. Personally identifiable information in learner questions is
**always redacted** before reaching the AI provider. Tutors sessions are
org-isolated and archived per learner.

### 4.6 AI Query Builder
**Query Builder** turns a plain-English question ("how many learners
completed a course this month?") into a safe, read-only SQL query over a
curated set of tables and shows the results as a table. Great for ad-hoc
questions without waiting for a report.

---

## 5. Exams & Assessments

**Exams** manages assessments per course:

- Question types: multiple choice, true/false.
- Time limit, passing score, and maximum attempts per learner.
- Publish/unpublish independently of the course.
- Passing an exam triggers certificate issuance automatically.

---

## 6. Managing Students

### 6.1 Users
**Users** lists everyone in your organization with role, activity and streak
information. Self-registered accounts are always learners; admin elevation is
invite-only.

### 6.2 Invitations
**Invitations** supports:

- **Single invites** — email a personal join link.
- **Cohort batch invites** — paste a list of emails and tag them with a
  cohort name. Cohort tags flow into analytics, digests and reports.

If outbound email is stubbed in your environment, you can copy the invite
link from the UI and share it manually.

### 6.3 Cohorts & celebrations
When a cohort crosses your configured completion threshold (default 75%),
the platform fires a celebration notification (optionally to a Slack/Discord
webhook) and includes the cohort in the Monday digest email.

### 6.4 Members Needing Action
The dashboard widget and weekly digest both surface learners who need a
nudge, with the reason (inactive, failing, deadline approaching). Use it as
your Monday-morning to-do list.

---

## 7. Learning Paths

**Learning Paths** chains courses into a sequenced journey (e.g. Foundation →
Intermediate → Advanced). Learners see their position on the path and unlock
the next step on completion. Paths can be edited or deleted at any time.

---

## 8. Live Sessions

**Live Sessions** manages instructor-led events:

- **Create a session** — title, time, meeting URL (any provider), linked
  course, capacity.
- **Recurring series** — weekly/monthly rules with exception dates; learners
  can RSVP to one occurrence or the whole series.
- **RSVP tracking** — see who's coming; learners who RSVP to a session of a
  course they aren't enrolled in are **auto-enrolled**.
- **Attendance** — mark attendance in the session modal (bulk mark
  supported). Attendance can automatically issue attendance certificates and
  send confirmation emails.
- **Calendar feeds** — learners subscribe via a personal ICS URL; you can
  rotate the URL secret org-wide if a link leaks.
- **Reminders** — automatic email reminders before each session.

---

## 9. Certificates

### 9.1 Issuance & branding
Certificates are issued automatically on exam pass or attendance. PDFs carry
your organization's branding (Section 1.3).

### 9.2 Public verification & sharing
Every certificate has a public verify link (QR code included on the PDF) and
a share page optimized for LinkedIn/Twitter previews — learners can brag,
employers can verify.

### 9.3 Revocation
Admins can revoke any certificate with a reason. Revoked certificates:

- fail public verification with the reason shown,
- return "410 Gone" if the learner tries to download the PDF,
- display a REVOKED banner on the share page and preview image.

Revocation can be undone. Every revoke/unrevoke is written to an **audit
trail** viewable per certificate.

### 9.4 Bulk operations
**Admin → Certificates** provides a searchable, filterable table with
multi-select **bulk revoke**, a per-certificate revocation-history drawer,
and a **CSV export** for auditors.

---

## 10. Gamification

- **Points (XP)** — learners earn points for activity.
- **Badge tiers** — configure your own tiers under **Badge Tiers** (name,
  threshold, icon); learners level up automatically.
- **Streaks** — daily learning streaks with automatic "streak about to
  break" nudge emails and a weekly streak leaderboard digest to staff.
- **Leaderboard** — org-wide ranking visible to learners.

---

## 11. Billing, Pricing & Payments

### 11.1 Setting prices
Set a price on any course (in cents, ZAR by default). Free courses enrol
instantly; priced courses route through checkout.

### 11.2 Payment providers
The platform supports a per-organization billing mode:

- **Native Stripe** — card checkout. In test environments Stripe runs in
  test mode (use card 4242 4242 4242 4242 — no real charges).
- **ERP360 billing bridge** — for organizations bolted onto ERP360's billing
  gateway (debit orders / lite-billing subscriptions).

### 11.3 Entitlements
Access is governed by an entitlement layer, not by the payment provider —
so switching providers never breaks existing learners' access. The
**Entitlements Inspector** shows exactly why a learner does or doesn't have
access to a course (paid, comp role, free course, etc.).

---

## 12. Marketing Tools

### 12.1 Public catalog & SEO
Published courses appear on your public catalog page with SEO-friendly URLs,
a sitemap and social-preview cards — indexable by search engines out of the
box.

### 12.2 Marketplace
Opt your organization into the cross-tenant **Marketplace** to have your
published courses discoverable by other academies' learners.
**Marketplace Analytics** shows views, clicks and conversion by course.

### 12.3 Affiliate / referral program
**Affiliate** lets you create referral codes (custom reward percentage,
expiry, notes). Copy the referral link, distribute it, and track referrals
and pending vs credited earnings. Payouts are marked credited by a super
admin. Self-referrals are automatically blocked.

### 12.4 Share & brag cards
Certificates and courses generate branded share pages with rich previews for
LinkedIn/Twitter — free word-of-mouth from every graduate.

---

## 13. Reports & Analytics

- **Reports** — enrolment, completion and certificate reporting with CSV
  export (cohort CSV includes per-learner progress).
- **Course funnel** — view → enrol → start → complete conversion per course.
- **Slide drop-off** — see exactly which slide loses learners.
- **Scheduled Reports** — subscribe yourself (or any recipients) to daily/
  weekly/monthly emails of four report kinds: members needing action, cohort
  progress, certificate issuance, enrolment summary. Run any report
  immediately with "Run Now".
- **Query Builder** — ad-hoc natural-language questions (Section 4.6).
- **Audit Log** — every significant admin action, searchable.

---

## 14. Communications

- **Email Diagnostics** — shows which email transport is active (per-tenant
  SMTP → system relay → bridge → stub) and lets you send a test email with
  immediate feedback.
- **Outbox** — every outbound email/webhook with status, retries and
  dead-letter queue; failed items can be re-queued.
- **Digests** — Monday cohort digest and streak-leaderboard digest to staff;
  learners receive reminders, celebrations and streak nudges automatically.

---

## 15. Integrations

- **API Tokens** — mint scoped, org-bound tokens for external systems to
  read your catalog via the public API. Tokens can be revoked or deleted.
- **Webhooks** — register outgoing webhooks (HMAC-signed) for events such as
  enrolment completed, certificate issued/revoked, AI budget threshold.
  **Webhook Deliveries** shows every delivery attempt with retries.
- **ERP360** — optional per-organization SSO and billing integration,
  configured under **Settings → Integrations** (super admin).

---

## 16. Settings & Compliance

- **Security** — change password, enable TOTP two-factor authentication
  (with recovery codes).
- **Terms & Conditions** — publish versioned T&Cs; learners must accept the
  current version before continuing (acceptance ledger records IP and user
  agent).
- **Kiosk mode** — for shared/front-desk devices: idle lock with PIN or
  password unlock.
- **Feature flags** — enable/disable individual platform features
  (AI authoring, marketplace, live sessions, affiliate program, etc.) per
  organization.
- **Preferences** — personal notification and digest opt-outs.
- **GDPR** — learners can request data export and erasure; erasure
  soft-deletes and anonymises while preserving certificate integrity.

---

## 17. Quick Troubleshooting

| Symptom | Check |
|---|---|
| Invite email never arrived | Email Diagnostics → transport status; copy the invite link manually |
| Learner can't see a course | Course status is PUBLISHED? Entitlements Inspector for that learner |
| Certificate shows invalid | Was it revoked? Check the revocation history drawer |
| Webhook not received | Webhook Deliveries → attempt log; verify the receiver returns 2xx quickly |
| AI builder fails | Organization AI budget exhausted, or platform AI key balance empty |

---

*IFPI Learning Platform — Administrator User Guide v1.0*
