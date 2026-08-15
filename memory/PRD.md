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

## 2026-08-11 (session 9) — Deployment readiness check
- deployment_agent run 1: BLOCKER — .gitignore blocked .env files required for deployment. FIXED: removed '.env', '.env.*', '*.env' from /app/.gitignore (backend/.env + frontend/.env now committable); added memory/test_credentials.md to .gitignore (note: file already tracked in earlier history).
- deployment_agent run 2: PASS with one WARN (unused [program:mongodb] in supervisord.conf — platform-managed infra, intentionally untouched, non-blocking).
- Pre-deploy switches for the user (documented, not changed): backend/.env ALLOW_TEST_TOKEN_HEADER=true is a TEST bypass → set false for production; PUBLIC_BASE_URL points at the preview URL → update to the deployed URL after deploy (affects cert share links/og-images); SQLite + ./uploads rely on persistent disk (Emergent deploy persists data per support).

## 2026-08-12 (session 10) — Pre-deploy safety pass (staff-testing deploy prep)
- User goal clarified: deploy a stable copy for a staff member to test, keep iterating in Emergent chat, push fixes via Update Deployment.
- backend/.env: ALLOW_TEST_TOKEN_HEADER=false (test bypass OFF everywhere, incl. future deploy); added AUTH_COOKIE_SECURE=true (auth cookies HTTPS-only). AUTH_COOKIE_MODE stays dual so login body still returns tokens (testing agent + legacy pytest unaffected).
- Code: settings.test_bypass_enabled (core/config.py) double-lock — env var AND non-production ENVIRONMENT — applied at all 5 bypass sites (routers/auth.py x2, core/middleware.py, routers/marketplace_analytics.py, routers/public_catalog.py).
- Verified: curl login OK (token in body, Secure/HttpOnly cookies), /_test/reset-rate-limit → 404, browser login → learner dashboard OK, pytest test_iteration22 + test_iteration32_sprint: 30 passed.
- README: new 'Deploying a staff-testing copy' section; env table updated. Details/runbook: /app/memory/deploy_notes.md.
- PENDING (post-deploy): user clicks Deploy → pastes live URL → set PUBLIC_BASE_URL to it → Update Deployment. To run legacy rate-limit pytest files, temporarily flip ALLOW_TEST_TOKEN_HEADER=true + restart backend.

## 2026-08-12 (session 10b) — Feedback screenshots + Welcome Tour
- Feedback widget renamed 'Report an issue': attach screenshot (file picker or paste, png/jpeg/webp ≤5MB) with preview/remove. New POST /api/feedback/screenshot (any authed, stores uploads/feedback/<uuid>) + screenshot_url on POST /api/feedback (validated '/feedback/' path). tester_feedback.screenshot_url column (alembic 7a8b9c0d1e2f). Admin /feedback-admin shows clickable thumbnails.
- WelcomeTour.tsx (components/): first-login spotlight walkthrough, once per user (localStorage ifpi_tour_done_v1_<userId>), 5 learner steps / 6 admin steps, skip/next/finish, targets scrollIntoView'd before highlight. Rendered in DashboardLayout.
- Verified: testing agent iteration_57.json — backend 8/8, frontend 100% (tour flows both roles, persistence, widget upload, admin thumbnails, validation 400/422/401). Post-test fixes: memoized tour steps (flakiness), scrollIntoView for off-screen nav targets (verified via screenshots). Backend tests: tests/test_feedback_screenshot.py.

## 2026-08-12 (session 10c) — Code review fixes (user-provided static analysis report)
- Investigated all findings first: circular imports = false alarm (already deferred imports); '36 undefined vars' = false positive (tsc clean, pyflakes clean); '16 high-sev security' = bandit found 0 high (mediums mostly false positives).
- Applied genuine fixes: SCORM manifest parsing hardened with defusedxml (XXE/entity-bomb rejected, verified); removed console.debug (ResearchPage); removed unused api_base (extras.py); deduped _delete_stale_certificates (test_debris_cleanup.py, kept the later/live def); int-cast id_csv (SQL hardening); tempfile.gettempdir() for staging/cache dirs (imports.py, docs_library_service.py); dropped no-placeholder f-strings (streak_digest_worker); removed inner os import (config.py).
- defusedxml added to requirements.txt (pip freeze). Docs regenerated (build_docs.py) for /api/feedback/screenshot route.
- SKIPPED by user-approved plan: 275/86/106 complexity-long-function refactors, 72 hook deps, 18 index-keys, TS coverage, file splitting (cosmetic, high regression risk pre staff-deploy).
- Verified: pytest 47 passed (debris cleanup, docs library, feedback, iter22 auth, docs completeness), backend healthy, XXE functional test pass.

## 2026-08-12 (session 10d) — User manuals v4.0 (comprehensive rewrite)
- Rewrote /app/docs/guides/ADMIN_USER_GUIDE.md + STUDENT_USER_GUIDE.md to v4.0: added Welcome Tour, exam gate, Attempts left + admin Reset attempts flow (w/ email), Question insights (miss-rate bars, distractor stats, TOP DISTRACTOR, author-alerted chip, re-arm on edit, Export CSV, in-place question edit), learner transcript PDF (My Certificates → Download PDF / Printable transcript), feedback screenshots (attach/paste, admin thumbnails), certificate share preview images; expanded troubleshooting tables. All button names verified against actual frontend code.
- PDFs auto-rebuilt via services/guide_builder ensure_fresh on download. Verified: both endpoints 200 (admin 12pp/42KB, student 7pp/22KB), pypdf text checks confirm all v4 content, test_public_guides.py 5/5 pass.
- Download URLs (anonymous): {BASE}/api/public/guides/IFPI_Admin_User_Guide.pdf and /IFPI_Student_User_Guide.pdf; also via sidebar Help & guides.

## 2026-08-12 (session 10e) — Guide screenshots embedded in manuals
- Captured 17 fresh screenshots (playwright, /tmp/capture_guide_shots.py) into /app/docs/screenshots/guide/*.jpg (1200w JPEG): login, admin dashboard/courses/editor/exams/attempts-modal/question-insights(with distractor stats + author-alerted)/users/settings/reports/feedback-inbox(with thumbnail)/admin tour, learner tour/courses/player(exam-gate banner)/certificates(transcript buttons)/feedback panel(attach screenshot).
- guide_builder.py: img + .fig caption CSS, link_callback for absolute local image paths. Figures embedded in both guides with numbered captions (Admin 12 figs, Student 6 figs).
- Verified: PDFs rebuild on download — Admin 17pp/778KB w/ 12 images, Student 9pp/424KB w/ 6 images; pymupdf page render confirms clean layout; test_public_guides 5/5 pass.
- Reminder for user: click Update Deployment to push v4.0 manuals + screenshots to the live URL.

## 2026-08-12 (session 10f) — Course delete flow
- CoursesPage: bin button on each card (visible only to course owner or SUPER_ADMIN via new created_by_id in CourseSummary). Published course → greyed bin + info toast 'Unpublish first'; draft → confirm modal (delete-confirm-modal) warning permanent, then DELETE /api/courses/{id}.
- Backend delete_course guards: 403 unless SUPER_ADMIN or created_by_id==current.id; 409 if status PUBLISHED; audit_service COURSE_DELETED entry added.
- Admin manual §5.6 'Deleting a course permanently' + troubleshooting row added (PDF auto-rebuilds).
- Verified: curl (409 published / 200 owner draft / 403 non-owner / created_by_id in list), UI screenshot (toast + modal + card removed), audit row present, regression 48 passed (iter2/3/47/48 incl. course-delete tests).

## 2026-08-12 (session 10g) — Course Archive feature
- POST /api/courses/{id}/archive (ADMIN/SUPER_ADMIN): 409 '{n} learner(s) are still busy with this course' when IN_PROGRESS enrollments exist; else status→ARCHIVED + COURSE_ARCHIVED audit. POST /{id}/unarchive restores to DRAFT (+audit). ARCHIVED enum value pre-existed; learners/catalog auto-hide (PUBLISHED-only filters).
- CoursesPage: archive button (box icon) on every admin card; archived cards show ARCHIVED chip + amber restore button; 'Show archived (n)' toggle next to search (archived hidden by default). Error toasts now read backend envelope error.message (was detail-only, busy message was invisible).
- INCIDENT (repeat of session-7 lesson): batched parallel search_replace on CoursesPage.tsx corrupted it (duplicated tail + reverted line). Fixed by removing orphan block + re-applying filter edit. RULE: never parallel-edit the same file.
- Cleaned TEST_Iter47/48 course debris from UAT org (scripts/cleanup_test_debris.py); restored 225/226 to PUBLISHED.
- Admin manual: new §5.6 Archiving (delete renumbered 5.7) + troubleshooting row.
- Verified: curl (409 busy w/ message, archive/unarchive/republish 200s, learner list hides archived), UI screenshots (busy toast, archive→hidden, show-archived, restore toast), tsc + webpack clean.

## 2026-08-12 (session 10h) — Slide image upload
- CourseEditPage: Upload button (slide-image-upload-btn) next to Media URL on IMAGE slides → POST /api/uploads/image (5MB cap, client-checked) fills media_url; live preview (slide-image-preview) below. data-testid slide-media-url added to URL input.
- Admin manual §5.2 step 3 documents slide pictures (URL / Upload / AI visual, swap, remove).
- Verified: UI screenshot flow — IMAGE chip reveals Upload, file upload sets URL + toast + preview; tsc clean. Course 224 left unchanged (not saved).

## 2026-08-12 (session 10i) — Slide image position + bulk photo upload
- CourseSlide.image_position (above|beside|behind, default above; migration 8b9c0d1e2f3a). SlideIn/SlideOut + all 3 SlideOut constructions + add/update_slide persist it (invalid values → keep/above).
- Editor: 'Picture position' chips under image preview (image-position-{above,beside,behind}); save() sends field. 'Add Photo Slides' bulk button (add-photo-slides-btn/input, multi-file) — uploads each, creates local IMAGE slide titled from filename, Save persists.
- Learner: LearnPage ImageSlideLayout renders 3 layouts (image-layout-above/beside/behind; behind = cover img + slate-900/60 overlay + prose-invert).
- BONUS FIX from testing-agent finding: POST /courses/{id}/enroll 500 (UNIQUE constraint) on concurrent double-enroll — now idempotent (IntegrityError → rollback → already:true). Verified with parallel curl.
- Tested: iteration_58.json — backend 5/5 pytest + full Playwright e2e 100% (picker persistence, bulk 3-photo, all 3 learner layouts, regression /learn/224, cleanup). Admin manual §5.2 updated (steps 4-5).

## 2026-08-12 (session 10j) — Learn page graceful 404
- User console log (prod): /learn/243 → GET/enroll 404s → LearnPage uncaught AxiosError (course was draft/deleted). CORS app.emergent.sh redirect on streak call = platform edge during redeploy, not app bug.
- LearnPage: loadError state → friendly 'This course isn't available' screen (course-unavailable testid) with Back to My Courses button, instead of infinite spinner + uncaught error.
- Verified: screenshot /learn/9999 shows friendly screen, back button navs to /courses, valid course 224 still loads. tsc clean.

## 2026-08-12 (session 10k) — Imported course + 'Edit course' shortcut
- User re-imported 'Utilizing the Fitness Facility (US 254459)' (course 243, 118 slides: 68 TEXT / 44 IMAGE / 6 VIDEO) into PREVIEW via Content imports Upload .zip — now part of committed snapshot, survives redeploys. COURSE 243 = REAL USER DATA — never save/delete/modify in tests.
- 'Bug': user in learner view expecting picture tools — tools were fine in editor. Fix: staff-only 'Edit course' button (learn-edit-course-btn) in LearnPage header → /courses/{id}/edit.
- Verified: iteration_59.json — 4/4 pass (button admin-only, editor tools work on imported IMAGE slides, learner hidden, friendly-404 regression). Prior context: prod data loss RCA (redeploy replaces prod disk/DB; workspace = source of truth; user OK, demo data only; persistent DB is go-live requirement).
- 10k addendum: Edit course button restyled bold solid indigo (user found tools; wanted bolder button). Screenshot verified.

## 2026-08-12 (session 10l) — Video autoplay on slide landing
- LearnPage: direct video files (mp4/webm/ogg/mov or /api/uploads paths) now render via AutoPlayVideo component (native <video> controls) — tries unmuted play(), falls back to muted if browser blocks; embeds keep iframe with allow=autoplay. serve_upload (iter5.py) mime map extended (mp4/webm/mov/m4v/ogg/mp3/wav/m4a/pdf/gif — was images-only, webm previously served as octet-stream).
- Verified: screenshot e2e — webm slide (58B Jogging) autoplays UNMUTED at t=3.76s. mp4 didn't decode in headless chromium (missing H.264 codec, test-env only — real Chrome fine, muted fallback engaged correctly).

## 2026-08-12 (session 10m) — Per-slide Edit shortcut
- LearnPage: staff-only 'Edit slide' button (learn-edit-slide-btn) next to slide title → /courses/{id}/edit?slide={slideId}. CourseEditPage reads ?slide= param, selects that slide and scrolls its rail row into view.
- Verified via screenshot e2e: slide 100 of course 243 → editor opens with '100. 58B Jogging' active + in view. Note: user has PUBLISHED course 243 themselves.

## 2026-08-12 (session 10n) — Return-to-slide after save
- CourseEditPage save(): when opened via ?slide= (from 'Edit slide'), after save navs back to /learn/{id}?slide={activeId} with toast 'Saved — taking you back to the slide'. Normal editor opens (no param) keep stay+Saved toast.
- LearnPage: supports ?slide= deep link — jumps current index to that slide on load.
- Verified via screenshot e2e round trip: learn slide 4 → Edit slide → Save → back on learn at 4/118 with toast.

## 2026-08-12 (session 10o) — Course progress memory (resume across devices)
- Enrollment.last_slide_index (migration 9c0d1e2f3a4b). POST /api/courses/{id}/progress {slide_index} clamps to slide count, stores index, bumps enrollment.progress = max(existing, (idx+1)/total*100) unless COMPLETED. /enroll responses now include last_slide_index.
- LearnPage: enroll response resume → setCurrent + 'Resumed where you left off' toast (skipped when ?slide= deep link present); slide changes saved with 600ms debounce (fire-and-forget).
- Note: BaseModel import needed adding to routers/courses.py (was missing → startup NameError, fixed).
- Verified: two fresh browser contexts e2e — device 1 navigates to slide 8, device 2 logs in and resumes at 8/118. Backend healthy, tsc clean.

## 2026-08-13 (session 10p) — Rich text editor + media transparency
- RichTextEditor.tsx (uncontrolled contentEditable): Bold/Italic/Underline, 9-colour foreColor palette (Range save/restore on mousedown), font-size dropdown (Small 0.85em / Normal / Large 1.4em via styled spans, Heading via formatBlock h3; execCommand fontSize=7 marker swapped to spans — added June 2026, verified via Playwright HTML inspection), text alignment buttons (justifyLeft/Center/Right → style text-align, verified rendering in learn view), bullet/numbered lists, clear formatting, raw-HTML toggle.
- SlideTemplates.tsx (June 2026): 6 ready-made slide layouts (Title, Title+Bullets, Step by Step, Two Columns via inline flex divs, Quote, Image+Text with image_position=beside). "From Template" button in CourseEditPage sidebar opens picker modal (data-testid slide-template-*); picked template creates a prefilled local slide. Verified E2E: templates save and render correctly through DOMPurify in learner view (flex columns + centred title confirmed via computed styles).
- BUG FIX (June 2026): "New Course" button silently did nothing when an "Untitled Course" draft already existed (backend 409 duplicate-title, createMut had no onError → unhandled rejection). handleNewCourse now auto-generates a unique title ("Untitled Course 2", 3…) and shows an error toast on failure. Verified: two consecutive clicks both navigate to the editor.
- CONTENT (June 2026): Module 1 videos — downloaded 3 Google Drive MP4s (1.6GB), transcoded to VP9 WebM (playable in all browsers incl. Playwright Chromium which lacks H.264), attached to slides 39/70/98 of course 243 (slide_type VIDEO, media_url /api/uploads/files/imports/327/vids/out{1,2,3}.webm, 265MB total). Course 243 PUBLISHED. Verified playback in learn view (autoplay + progress bar). NOTE: /api/uploads/files serving ignores Range headers (200 full-body) — seeking is limited; fine for progressive playback.
- AI TUTOR FIX (June 2026, user-reported prod Cloudflare 524): (1) hard timeouts — embed_texts 90s→20s, LLM chat calls asyncio.wait_for 60s → friendly 504 (ai_tutor.py, tutor_service.py) so the endpoint can never exceed Cloudflare's 100s edge limit; (2) Module 1 (course 243) had NO tutor sources → 99 slide transcripts ingested as SourceDocument id 50 (77k chars, embedded) — tutor now answers with 4 citations in ~5s. Verified iteration_66 (8/8 backend + frontend E2E incl. Save-as-flashcard). Original 524 was old prod build + London DB; republish carries all fixes.
- SCALE-HARDENING SWEEP (June 2026, user-approved full plan for high-volume launch, iterations 64-65 all 100%):
  - Phase 0: scripts/load_test.py (concurrent learner simulator, history in /app/memory/load_tests.json). Baseline: 30 users, p50 600-1400ms, 33 rps.
  - Phase 1: N+1 fixes (courses list/detail counts via aggregates), HTTP Range support in serve_upload (206/416, video seeking). Gate: iteration_64 100%.
  - Phase 2 (mypy): mypy.ini gradual config (legacy-Column noise codes disabled, strict on new services); 762→81 residual errors; 2 REAL bugs fixed (certificates bulk-email crash on deleted LiveSession; auth SSO form-post crash on file part).
  - Phase 3 (cache): core/cache.py — in-process TTL cache, auto-switches to Redis when REDIS_URL set. Applied: get_current_user 30s (invalidate_current_user_cache on ERP role sync/deactivation), catalog 60s (invalidated on all course lifecycle mutations via _get_owned + crud create/update), leaderboard 15s, admin analytics 30s. Results: catalog 997→3.8ms, leaderboard 796→4.2ms, ~200ms saved per authed request, 33→58 rps.
  - Phase 4 (API v2): routers/api_v2.py — additive /api/v2 with {data, meta} envelope (health, courses, courses/{id}, enrollments, catalog); v1 untouched.
  - Phase 5 (Vite): ABORTED — support_agent confirmed Emergent deploy pipeline only supports CRA conventions (REACT_APP_* injection, build/ output). Keep CRA.
  - REGION MOVE COMPLETE (June 2026): DB migrated London → **Neon us-east-2** (ep-patient-cake-ayzez99t, user-created project). 74,566 rows, 0 orphans, sequences reset, alembic stamped, DATABASE_URL flipped. RTT 99ms→26ms. Load test: 33→187 rps, p50s 600-1400ms→130-270ms, 0 errors. 48/48 pytest regression (now runs in 29s vs 100s). Old London project can be deleted by user once live site confirmed. TEST_iter65_* leftover courses cleaned up.
  - KNOWN BOTTLENECK: Neon is in eu-west-2 (London), servers in US → ~99ms per query = ~600ms API floor. (RESOLVED by region move above) User approved region move (option b: agent handles it via Neon API key) — WAITING for user to paste Neon API key (console.neon.tech → API keys). When received: create project in aws us-east-1, pg_dump/restore or rerun migration, flip DATABASE_URL, restamp alembic, full regression.
- AUDIT REMEDIATION SWEEP (June 2026, user-approved "full sweep" after Kimi audit review):
  - Phase 1: routers/misc.py (1391 lines) split into 8 domain routers (ai, enrollments, certificates, notifications, gamification, admin_analytics, billing, catalog); routers/courses.py (950 lines) → package routers/courses/{common,crud,ratings,slides,enrollment,prerequisites}.py sharing ONE router via common.py (registration order preserved — /reorder before /{course_id} etc.); _can_manage deduped into auth.dependencies.can_manage_content.
  - Phase 2: business logic extracted to services/enrollment_service.py (enroll/progress/complete) and services/course_lifecycle_service.py (delete/publish/unpublish/archive/unarchive/duplicate/featured). BUG FIX: duplicate_course now copies image_position + media_opacity.
  - Phase 3: frontend — all routes React.lazy code-split w/ Suspense; new components/ErrorBoundary.tsx wraps app (data-testid error-boundary); App.tsx rewritten; removed `any` in DashboardPage activity map.
  - Phase 4: server.py startup logs CRITICAL warnings if production boots with jwt_secret=change-me / CSRF off / insecure cookies. (Error envelope already unified via global handler; success-shape changes intentionally skipped to avoid breaking frontend. Vite/Redis/mypy-strict intentionally rejected.)
  - Regression: iteration_63.json — 28/28 backend, 100% frontend, zero console errors. Suite: backend/tests/test_iter63_refactor_regression.py.
  - Audit P0s were already satisfied pre-sweep (CSRF_ENABLED=true, AUTH_COOKIE_SECURE=true, real JWT_SECRET all set in shipped .env; StrictMode present; defusedxml pinned).
- MIGRATION COMPLETE (June 2026): **PostgreSQL (Neon) + Emergent Object Storage are LIVE.**
  - DATABASE_URL in backend/.env → Neon (ep-blue-pine-zal6qd5o, eu-west-2). 74,259 rows migrated from SQLite via scripts/migrate_to_postgres.py (123 orphan rows skipped — stale billing/revocation test artifacts). Sequences reset, alembic stamped head. Old SQLite file kept at /app/backend/ifpi_lms.db as a backup snapshot.
  - STORAGE_BACKEND=emergent → new EmergentStorage class in services/storage_service.py (objstore proxy API w/ EMERGENT_LLM_KEY, write-through local disk cache at uploads/, local_path() for FileResponse serving). All 801 upload files pushed via scripts/push_uploads_to_objstore.py (4 transient 500s retried OK). Verified: cache-miss → fetched from objstore → cached → served (200).
  - Preview and production now SHARE the Neon DB + object storage → live-site data persists across redeploys; the "wiped on republish" era is over. Media URLs unchanged (/api/uploads/files/...).
  - Regression: iteration_62.json — 20/21 backend pass (1 non-blocking skip), 100% frontend critical flows, zero 500s. Reusable suite: backend/tests/test_iter62_pg_migration.py.
- IN PROGRESS (June 2026): Production persistence — user chose NEON Postgres; waiting for connection string. (SUPERSEDED by migration above) psycopg2-binary installed (requirements.txt updated). Emergent Object Storage playbook obtained (proxy via /objstore API, EMERGENT_LLM_KEY auth, no presigned URLs — serve through backend; plan: new backend in services/storage_service.py behind get_storage() with local disk cache, migrate uploads tree, then flip DATABASE_URL to Neon via schema create_all + data copy + sequence reset + alembic stamp).
- CONTENT (June 2026): Imported "Module 1: Anatomy & Physiology" (course id 243, DRAFT, org 327) into PREVIEW from user's SCORM ZIP — 99 IMAGE slides (slide jpg + cleaned transcript text, nav artifacts "Back/Next/Section Navigation" stripped). Media stored under uploads/imports/327. Fixed &amp; double-escaping in titles. Video slots at slides 39/70/98 have no MP4s (user may add via editor). One-off conversion script (not kept in repo) parsed slides.js from the SCORM package.
- BUG FIX (June 2026): ZIP import silently found nothing (COMPLETED 0/0) when the ZIP's single top-level dir was `courses/` itself — the macOS-unwrap logic descended INTO it looking for courses/courses. Fixed: (1) upload-zip never unwraps into a dir named courses/paths, (2) _resolve_content_root() in bulk_import.py finds the real content root at run time (handles pointing straight at courses/, one wrapper level), (3) 0-item runs now finish FAILED with a helpful error_log instead of a misleading COMPLETED. Verified: courses-topdir ZIP → COMPLETED 1/1; direct courses/ path → COMPLETED; empty tree → FAILED + message.
- FEATURES (June 2026): (1) Import Retry — POST /api/admin/imports/{id}/retry re-runs FAILED/PARTIAL jobs from the same staging dir (410 if dir gone); Retry button (data-testid import-retry-{id}) on ImportsPage. Verified: FAILED job retried → COMPLETED, missing-dir → 410. (2) Video auto-advance — AutoPlayVideo onEnded advances to next slide (skipped on last slide to avoid auto-completing); verified via dispatched 'ended' event (slide 1/118 → 2/118 + toast).
- CHANGE (June 2026): Course delete permission relaxed — any org ADMIN (or SUPER_ADMIN) can now delete any course in their org; previously only the course *owner* could, which made imported courses (owned by internal migration@ user) undeletable by real admins. Backend owner-check removed in delete_course; frontend canDelete now role-based. Unpublish-before-delete rule unchanged. Delete 404s now gracefully refresh the course list (stale-cache UX). DATABASE_URL made absolute (sqlite:////app/backend/ifpi_lms.db) to prevent split-brain DB files if server CWD differs.
- BUG FIX (June 2026): Bulk content re-import (Content Imports page) FAILED with "FOREIGN KEY constraint failed" when re-importing a course whose slides had learner activity (slide_views etc.) — import_course_from_directory bulk-wiped course_slides without detaching dependents. Now deletes SlideView/SlideComment rows and NULLs Flashcard/ScormPackage slide_id for old slides first (mirrors delete_slide fix). Reproduced + verified via /api/admin/imports/run on a synthetic course with a slide_view (FAILED before → COMPLETED after). This was the production issue "import ran but course doesn't show".
- BUG FIX (June 2026): DELETE /api/courses/{id}/slides/{slide_id} 500'd with FK IntegrityError when the slide had slide_views/comments/flashcards/scorm rows. delete_slide now removes SlideView+SlideComment rows and NULLs Flashcard/ScormPackage slide_id before deleting (slide_versions already CASCADE). Verified via curl (200). Replaces plain HTML textarea in CourseEditPage (keyed per slide). NOTE: initial controlled version reversed typing (caret reset per render) — fixed by uncontrolled pattern (iter60 CRITICAL → iter61 100% pass).
- CourseSlide.media_opacity (20-100, migration a0d1e2f3a4b5), clamped in add/update_slide, in all SlideOut sites. Editor: Media transparency slider for IMAGE/VIDEO slides + live preview dim. Learner: opacity applied in ImageSlideLayout (3 layouts), AutoPlayVideo, video iframe.
- Tested: iteration_60 (backend 4/4 media_opacity incl clamps; transparency e2e pass; RTE critical bugs found) → fix → iteration_61 (4/4: typing order, bold+red markup, learner render survives DOMPurify, cleanup). tests/test_media_opacity.py added by testing agent. Manual §5.2 updated (toolbar + transparency).
