# IFPI Learning Platform — Roadmap

Prioritized backlog. Completed items live in `CHANGELOG.md`.
**➡️ For the go-live checklist (all infra + integration items still open before we can flip prod), see `/app/memory/GO_LIVE_CHECKLIST.md`.**

## P0 — Go-live blockers
_See `/app/memory/GO_LIVE_CHECKLIST.md` — every P0 item lives there
(deploy, secret rotation, CORS_ORIGINS setup, ERP360 tile flip,
browser click-through smoke test on deployed URLs, infra provisioning:
Neon Postgres, Cloudflare R2, Resend SMTP, Sentry DSN, staff dogfooding)._

## P1 — Should close before or shortly after cutover
_Also tracked in `GO_LIVE_CHECKLIST.md`:_
- §7.4 per-org connection state (retire global `SSO_ENABLED`)
- §7.1 entitlement abstraction (blocks Stripe rework)
- §7.2 verified-email link tightening on JIT first-link
- §6.3 timestamp replay window (±5 min on `X-ERP360-Timestamp`)
- `/api/v1/` versioning namespace with unversioned aliases ≥1 sprint
- SQL-backed idempotency store for `X-ERP360-Event-Id` (currently in-memory)
- Stripe integration (only if commercial launch; depends on §7.1)

## P2 — Nice to have
- **§4 Outbound webhook dispatcher (IFPI → ERP360)** — sender for
  `learner.invited`, `enrollment.completed`, `certificate.issued`,
  `ai.spend.threshold`, `course.published`. Depends on ERP360 exposing
  their inbound receiver + shared `X-IFPI-Signature` HMAC secret.
  Highest-value event is `certificate.issued`.
- **§P1.1 ERP360 lite-billing mode** — writes into the same
  `Entitlement` table as native Stripe.
- **Flip `USE_PGVECTOR=true`** after ~1000 chunks (migration prepped).
- **Multi-language support** on the learner UI.
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
