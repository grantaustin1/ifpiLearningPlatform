# IFPI Learning Platform — PRD

Multi-tenant LMS built on the ERP360 tech stack (FastAPI + SQLAlchemy + React 19).

- **Iteration history** → `/app/memory/CHANGELOG.md`
- **Backlog (prioritized)** → `/app/memory/ROADMAP.md`
- **Test credentials** → `/app/memory/test_credentials.md`

## Original problem statement
Assess the ERP360 and IFPI Next.js codebase and build the IFPI learning app as a sibling application. Rebuild IFPI using the ERP360 tech stack. Support:

- Multi-tenant Organizations with JWT-based Auth
- AI Course + Quiz Builder (Emergent LLM Key)
- S3 configuration (currently MOCKED)
- SCORM / xAPI support
- Slide Versioning + Bulk Imports
- Outgoing HMAC Webhooks
- SSO + API Tokens
- Comprehensive AI Authoring Suite

## User personas
- **Super Admin (SaaS)** — cross-org configuration, marketplace curation.
- **Organization Admin / Instructor** — creates courses, assigns to cohorts,
  moderates live sessions, marks attendance, views funnel + drop-off analytics.
- **Learner** — enrolls, plays slides, RSVPs to live sessions, earns badges +
  certificates, keeps a learning streak.
- **API-token principal** — external integrations calling the read-only
  catalog API with scoped credentials.

## Core requirements (invariants)
1. **Multi-tenant** — every row scoped by `organization_id`. Cross-tenant
   endpoints (marketplace, public catalog, public certificate verify) are
   explicit and read-only.
2. **HttpOnly Cookie auth** in production (JWT bearer for tests only, gated
   by `ALLOW_TEST_TOKEN_HEADER=true`).
3. **Rate limiting** on public endpoints (login, verify, marketplace).
   Client IP resolved via `X-Forwarded-For` (K8s ingress) with test-only
   `X-Test-Client-Ip` override.
4. **Idempotent writes** wherever a background retry might replay
   (attendance certificates, notifications, outbox webhooks).
5. **All ObjectId/PK values serialized as JSON-safe strings**; datetimes
   in ISO-8601 UTC.
6. **PDF branding** — certificates inherit org's logo, primary colour,
   signature block, and footer text.
7. **Documentation drift protection** — every new endpoint must appear in
   `IFPI_USER_MANUAL.md` after running `python backend/scripts/build_docs.py`.

## Health snapshot (2026-02, post iter-39)
- Backend routes: 260+ endpoints (auto-indexed in the manual). Every endpoint reachable under BOTH `/api/*` and `/api/v1/*` (Iter 39 versioned alias middleware).
- Frontend: React 19, 65+ pages/components.
- Background workers: outbox drain, webhook retry, cohort celebrations,
  weekly digest, live-session reminders, nightly test-debris cleanup,
  streak-break nudge (Iter 27), scheduled reports, streak leaderboard
  digest (Iter 30), compliance auto-report (Iter 31, env-gated),
  progress-outbox drain @ 2s (Iter 38 Phase B).
- Scalability guards (Iter 38 A/B/C): per-request query-count middleware,
  N+1 fixes on 4 hot endpoints, retry-on-deadlock on mutations,
  in-process TTL cache (`X-Cache: HIT|MISS`) + graceful-degrade on
  `/api/erp360/sync/status`, `/api/feature-flags`, `/api/public/catalog`,
  circuit breaker on certificate PDF generation.
- Integration hardening (Iter 39): per-org SSO enablement retires global
  `SSO_ENABLED`; ERP360 claim-side `email_verified` required for
  native-account auto-linking; `EntitlementService` decouples enrollment
  from payment-provider specifics; Stripe test-mode wired end-to-end;
  outbound webhook dispatcher IFPI → ERP360 operational in dry-run
  (auto-provisions on org PATCH; flip URL to go live).
- Storage: SQLite (dev + preview) at absolute path
  `sqlite:////app/backend/ifpi_lms.db`. Postgres migration deferred to P2.
- Tests: 585+ pytest tests + 50+ Playwright E2E flows via
  `testing_agent_v3_fork`.

## Related docs
- `IFPI_USER_MANUAL.md` — auto-generated API + model index
- `IFPI_SETUP_MANUAL.md` — role matrix + deployment setup
- `IFPI_INTEGRATION_MATRIX.md` — third-party integration status
- `IFPI_WEBHOOK_EVENTS.md` — outgoing webhook payload reference (Iter 31)
- `IFPI_VS_ERP360_ASSESSMENT.md` — original assessment
- `docs/P2_BACKLOG_SPECS.md` — deep-dive specs for deferred items

## 2026-08-06 (session 2) — Correct merge resolution + full regression green
- DISCOVERY: branch 20260731's broken merge had two divergent parents. The GitHub/Copilot CI line (6d926451, previously restored) had silently DROPPED iterations 42-48 (CourseRating model, covers/featured, reviews, reply/share, landing analytics) during a router-decomposition refactor, and wrongly reverted the Iter-40 fitness rebrand. The Emergent dev line (b7ce3738, 2026-08-01) is the complete app.
- RESOLUTION: working tree switched to b7ce3738 (dev line) as base; removed 70 stale decomposition-package files (routers/misc/, routers/courses/, etc.) that shadowed the monolithic routers; kept backend/conftest.py + pytest.ini for local pytest runs.
- Env restored per repo changelog: CSRF_ENABLED=true, AUTH_COOKIE_MODE=dual, ALLOW_TEST_TOKEN_HEADER=true, SMTP_ENCRYPTION_KEY, SSO_ENABLED=true, ERP360_SSO_SHARED_SECRET, IFPI_WEBHOOK_OUTBOUND_SECRET, STRIPE_API_KEY, EMERGENT_LLM_KEY.
- Stale-test fixes (code was newer than tests on the dev snapshot): iter6/8 theme slugs (conservatoire→crimson_gold per fitness rebrand), iter30e docs manifest (+erp360-bolt-on, line_count>40), iter23 cleanup dict (+marketplace_optouts), iter23 tavily error envelope, iter26 track-view/dropoff (async outbox semantics), iter36 SSO tokens (+email_verified claim per iter39 tightening), ifpi_api sso_disabled (SSO now enabled), iter24 tampered-token (base64 spare-bit no-op), iter29 rate-limit (pinned bucket+session), iter13 digest tests (isolate from factory orgs), iter4 outbox pagination (page 999999). Added module-scoped debris-purge fixtures to iter41/42/43 catalog tests.
- FULL REGRESSION: 843 passed / 6 skipped / 0 failed (was 101 failed + 48 errors at session start).
- Frontend: tsc clean, full marketplace UI (hero, featured row, native course cover art) verified in browser; admin login + forced password-change gate working.
- NOTE: .env files are gitignored — required env keys are documented above and in memory/DEPLOY_RUNBOOK.md.

## 2026-08-06 (session 3) — README env guide + learner-journey smoke tour
- Created /app/README.md with full env setup guide (backend/.env + frontend/.env key tables, quickstart, test-suite instructions, test accounts).
- Testing-agent browser smoke tour (iteration_49.json): full learner journey GREEN — landing/catalog (covers, no debris), login, course detail, enrol, player, completion, certificate issuance, PDF download, public verify UI + API.
- Fixed the one UI regression found: player sidebar progress stuck at 20% after Complete (LearnPage.tsx next() now marks all slides complete). Verified by testing agent (iteration_50.json, 100%).
- Known minor items (not fixed, cosmetic/noise): anon pages log a 401 from /api/auth/me probe; learner cert history contains old TEST_iter27/28 debris certificates.

## 2026-08-06 (session 4) — Cert cleanup, silent auth probe, exam gate
- Debris cleanup service: added `TEST_%` live-session pattern + new `_delete_stale_certificates` step (pattern-matched & orphaned live-session certs, incl. revocation events); runs before session purge; idempotent. Purged 103 debris certs + 93 TEST_iter27/28 sessions from the DB. tick() stats dict now includes "certificates" (test updated).
- AuthContext: /auth/me probe now gated by localStorage 'ifpi_session_hint' (set on login/register/2FA/SSO, cleared on logout/401) — anonymous pages no longer fire the probe, killing the 401 console error.
- Exam gate (Iter 49): CourseDetail now returns exam_id/exam_title/exam_passed (published exam + caller's passed state). LearnPage last-slide button becomes 'Take exam' and routes to /take/{exam_id} when unpassed; TakeExamPage completes the linked course + issues the certificate on pass ('View Certificate' btn), failed attempts get 'Review the course'. Backend POST /complete unchanged (UI-level gate) so existing API tests remain valid.
- Verified: testing agent iteration_51.json — all fixes PASS (cert history clean, zero anonymous /auth/me calls, gate flow passes exam 4 at 100% and issues cert, already-passed shortcut OK). Targeted backend regression: 78 passed.
- NOTE: 'Save to GitHub' is a user-side platform button — user directed to use it.

## 2026-08-06 (session 5) — Attempt reset, exam banner, share PNG, transcript page
- Attempt Reset (Iter 50): GET /api/exams/{id}/attempts (per-learner summary) + POST /api/exams/{id}/attempts/reset (admin/instructor, audited as EXAM_ATTEMPTS_RESET). ExamsPage 'Attempts' button opens AttemptsModal with per-learner reset + confirm dialog.
- Exam Progress Banner: LearnPage shows amber exam-gate-banner on every slide of gated (un-passed) courses; disappears once the exam is passed.
- Cert Share Images: new GET /api/certificates/verify/{code}/og-image.png (Pillow 1200×630 branded card, revoked band supported; reportlab Vera fonts). seo.py share page og:image switched from .svg to .png (LinkedIn doesn't render SVG). PUBLIC_BASE_URL set in backend/.env so og:image URLs are public https.
- Learner Transcript: GET /api/certificates/transcript.json + /transcript printable page (courses w/ best scores, certificates w/ verify codes + Valid/Revoked, badges, print & back buttons, print:hidden chrome). CertificatesPage now has 'Printable transcript' + 'Download PDF' buttons.
- New QA admin account qa-admin@ifpi.org / QaAdmin!2026 (must_change_password=False) — seeded admin's forced-change flag is asserted by test_iteration32 and must stay. Recorded in memory/test_credentials.md.
- Verified: testing agent iteration_52.json — all 4 features PASS (UI + curl). Docs regenerated; targeted backend tests green (docs drift, iter8/28/29: 43 passed).

## 2026-08-06 (session 6) — Reset notifications + question insights (Iter 51)
- Reset Notification: reset_exam_attempts now queues an outbox email (template exam_attempts_reset, branded HTML, retake CTA) via MailService AND an in-app bell notification (EXAM_ATTEMPTS_RESET, link /take/{examId}) via GamificationService.notify. Best-effort try/except so mail failures never block the reset. Email transport remains dev STUB (queued in outbox, not delivered) by design.
- Attempt Insights: new GET /api/exams/{id}/question-insights (admin/instructor) — per-question answered/correct/missed + miss_rate using the canonical grade_question, sorted most-missed first. AttemptsModal now has 'Learners' / 'Question insights' tabs with colored miss-rate bars (red ≥50, amber ≥25, green else).
- Docs regenerated for new route. Verified: testing agent iteration_53.json — both features PASS (UI + API + outbox + bell), learner state restored (exam 4 re-passed 100%). Targeted backend tests green (docs drift, iter4/15: 28 passed).

## 2026-08-06 (session 7) — Insight Actions (Iter 52)
- New PATCH /api/exams/{exam_id}/questions/{question_id}: in-place single-question edit (question_text, options, correct_answer, explanation, points) — preserves question id so attempt history and insights stay linked (unlike PUT /questions replace). Audited as EXAM_QUESTION_EDITED. Insights response now also returns options/correct_answer/explanation/course_id.
- ExamsPage insights tab: 'Edit course content' header link → /courses/{course_id}/edit; per-row 'Edit' button opens EditQuestionModal (MC radio for correct option, TF toggle w/ aria-pressed, short-answer input, points, explanation).
- Verified: testing agent iteration_54.json — all PASS (UI flows, persistence via API, ids unchanged, history preserved, regression clean). Docs regenerated.
- INCIDENT NOTE: parallel search_replace calls on the same file (routers/exams.py) corrupted it mid-session; restored from auto-commit 7311c8a2 and re-applied edits sequentially. Rule: never batch multiple edits to one file in parallel.
- Save to GitHub: user-side platform button; user reminded to click it.

## 2026-08-07 (session 8) — Distractor stats, CSV export, miss-rate alerts (Iter 53)
- Distractor Stats: question-insights now returns answer_distribution (per picked answer: label/count/is_correct) + top_wrong; UI shows per-option bars (green ✓ correct, red TOP DISTRACTOR badge on most-picked wrong option).
- Insight Export: GET /api/exams/{id}/question-insights.csv (admin/instructor, text/csv; charset=utf-8, attachment) + 'Export CSV' button in the insights header (blob download).
- Miss Rate Alerts: exam_service._check_miss_alerts runs after each attempt — questions with ≥50% miss rate over ≥3 answers fire in-app QUESTION_MISS_ALERT notifications + queued question_miss_alert emails to all org INSTRUCTOR/ADMIN/SUPER_ADMIN. Dedup via new exam_questions.miss_alerted_at column (alembic 6f7a8b9c0d1e); editing a question clears it (re-arms). Insights rows show '· author alerted' chip.
- Verified: testing agent iteration_55.json — all PASS (UI + curl + outbox + re-arm; learner deliberate-fail path). State note: learner now 3/3 attempts on exam 4 (still Passed, best 100%) — use admin Reset if a fresh attempt is needed. Docs regenerated; targeted tests green.
