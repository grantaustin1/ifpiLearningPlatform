# IFPI Learning Platform — Roadmap

Prioritized backlog. Completed items live in `CHANGELOG.md`.

## P0 — Next up
_Nothing currently blocking; iter-30 shipped 5 planned items + 1 UX
improvement (bulk certificate operations). Waiting on user for next
sprint._

## P1 — High value
- **Absolute SQLite path** — flip `DATABASE_URL` from `sqlite:///./ifpi_lms.db`
  to `sqlite:////app/backend/ifpi_lms.db` so pytest from any cwd hits
  the right DB. Prevents the iter-30 stale-fixture flake.
- **Bulk-revoke reason modal** — replace `window.prompt()` in
  `AdminCertificatesPage` with an in-brand text-input modal.
- **HR-system webhook payload docs** — publish an `IFPI_WEBHOOK_EVENTS.md`
  documenting `certificate.revoked` + `certificate.unrevoked` payload
  shape for external integrators.
- **Bulk unrevoke + bulk email + bulk download-zip** — extend the
  admin-certs table with reverse bulk ops (currently only revoke).
- **Streak-digest opt-out** — some admins may not want the weekly
  email; per-user preference or org toggle.

## P2 — Nice to have
- **pgvector migration** for advanced RAG on AI Tutor. Spec in
  `docs/P2_BACKLOG_SPECS.md`. Deferred — massive storage engine swap.
- **Multi-language support** on the learner UI. AI Authoring already
  supports auto-translate of slides.
- **Instructor Insight Nudges** — highlight slides with >50% drop-off
  automatically in a weekly Slack/email digest (backend data exists;
  worker + notification needed).
- **Cohort auto-enrol from live-session RSVP** — reverse of Iter 24's
  auto-RSVP; RSVP'ing to a live session in a course you're not enrolled
  in should offer inline enrolment.

## P3 — Wishlist
- **SCORM 2004 export** (we currently import + play; export is
  authoring-only).
- **AI Tutor with retrieval-augmented responses** — depends on P2 pgvector.
- **Mobile push notifications** via FCM/APNs for streak nudges + session
  reminders. (In-app notifications already exist.)
- **Instructor-side webhook builder UI** — currently webhooks are
  configured via API only.

## Refactoring backlog
- **`server.py` decomposition** — 500+ lines; router registration could
  move to `core/routers.py`.
- **`models/__init__.py` splitting** — 1200+ lines. Split by domain
  (auth.py, courses.py, live_sessions.py, gamification.py).
- **Frontend page directory reorg** — group dashboard subpages by
  domain (already started with `live-sessions/`).

## Deferred / dropped
- **Native mobile app** — dropped. Progressive Web App path is preferred.
- **Live-video recording** — dropped. Learners can RSVP + join via any
  meeting URL; recording remains the meeting provider's responsibility.
