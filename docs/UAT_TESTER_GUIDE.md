# IFPI Learning Platform — UAT Tester Guide

Welcome! You're testing in an **isolated sandbox tenant** ("UAT Sandbox").
Everything you create is invisible to other organizations and will be wiped
before go-live — so break things freely.

## 1. Where & who

**URL:** https://last-checkpoint-15.preview.emergentagent.com

| Role | Email | Password |
|---|---|---|
| Admin (you, most of the time) | `uat-admin@ifpi.org` | `UatAdmin!2026` |
| Learner (for the student flow) | `uat-learner@ifpi.org` | `UatLearner!2026` |

Tip: use two browsers (or one normal + one incognito window) to stay logged
in as admin and learner simultaneously.

## 2. Suggested test script

### As Admin
1. **Branding** — Settings: set org colour, logo, certificate signature/footer.
   Watch the onboarding checklist on the dashboard tick off as you go.
2. **Create a course manually** — Courses → New: add slides, set passing
   score, duration, price. Publish it.
3. **Create a course with AI** — use the AI Course Builder (give it a topic;
   it drafts slides + quiz). Also try the AI quiz generator on your manual
   course, and edit/regenerate slides. *(AI features consume real LLM
   credits — go wild, but not infinitely wild.)*
4. **Take on students** — Invitations: invite a learner (or a real teammate
   email); try a cohort batch invite. Check the user list.
5. **Pricing & billing** — set a price on a course (ZAR cents). Billing runs
   in **test mode**: checkouts use Stripe test cards — use card number
   `4242 4242 4242 4242`, any future expiry, any CVC. **No real money moves.**
6. **Marketing tools** — try the affiliate/referral codes page (create a code,
   copy the referral link), scheduled reports, the public catalog/SEO share
   pages, and certificate share/brag cards.
7. **Live sessions** — schedule a session, RSVP as the learner, mark
   attendance, watch the attendance certificate fire.

### As Learner
1. Log in as `uat-learner@ifpi.org` (or self-register a fresh account at
   `/register` — new signups are learners automatically).
2. Browse the catalog, enrol in your published course (pay with the test card
   if priced), play through the slides, ask the **AI Tutor** a question.
3. Take the exam, pass it, download the certificate, check the public
   verify link and the share page.
4. Check streaks/points/badges on the dashboard.

## 3. What's stubbed / good to know
- **Email**: outbound email may be in stub mode (check Admin → Email
  Diagnostics → transport status; there's a "send test email" button).
  Invitation links still work — the admin can copy them from the UI.
- **File storage** is local/mocked in preview (uploads work, but this isn't
  the production bucket).
- **Payments**: Stripe **test mode** only. Real card numbers will be declined.
- The admin account skips forced password change and email verification —
  already handled.

## 4. Reporting issues
Note the page, what you clicked, what you expected vs got, and a screenshot.
Timestamps help — backend logs are retained.

## 5. Cleanup (for the dev team, not the tester)
- Everything lives in org `uat-sandbox` (id 327) — isolated by design.
- Full factory reset: `bash /app/scripts/reset_uat.sh` (restores the
  2026-07-30 pre-UAT snapshot; wipes all UAT activity).
- Production go-live uses a fresh database anyway — nothing here migrates
  unless we deliberately export it.
