# P2 Backlog — Detailed Specs

**Purpose:** Next-session pickup docs for the four large P2 features not implemented in Iter 30q. Each spec includes scope, table plan, endpoint plan, and an estimate. Written in the style used for successful iters (30h-30q).

---

## 1. Affiliate / Referral Program (P2 · est. 2-3 days)

### Value
Turn happy admins into a distribution channel. Every org can generate referral codes; when a new org signs up with that code, both sides get billing credit.

### Tables
```
affiliate_codes
  id, organization_id (owner), code (unique), reward_bps (default=1000 = 10%),
  cap_credits_cents (default=null), expires_at, is_active, created_at

affiliate_referrals
  id, code_id, referred_organization_id, signed_up_at,
  credit_cents (computed at conversion), status (PENDING|CREDITED|REJECTED),
  credited_at, notes
```

### Endpoints
```
POST /api/admin/affiliate/codes           — create a code
GET  /api/admin/affiliate/codes           — list mine
POST /api/register?ref=<code>             — thread through registration
GET  /api/admin/affiliate/referrals       — see who signed up
GET  /api/admin/affiliate/earnings        — total pending/credited
```

### Flow
1. Admin creates code, gets a shareable URL (`{app}/register?ref=CODE`).
2. New org registers via that URL — registration handler records `affiliate_referrals` row in PENDING state.
3. On first paid Stripe invoice for the new org → cron sets status=CREDITED, dispenses credit against the owner's next invoice via the existing `billing_service`.

### Watch out for
- Fraud: self-referral (same admin, different email) must be blocked. Compare IP + email domain.
- Reward calculation must respect existing billing cycles — piggyback on the pending invoice, not stub.
- Terms disclosure: an "Affiliate T&Cs" version must be accepted before payout.

---

## 2. Marketplace (P2 · est. 4-5 days)

### Value
A public catalog where orgs can list courses for sale to other orgs, generating a new revenue stream + network effects. Kimi's plan didn't cover this — it's IFPI-native.

### Tables
```
marketplace_listings
  id, organization_id (seller), course_id, price_cents, currency,
  is_active, description_markdown, cover_image_url, sample_slide_ids (JSON),
  listed_at, updated_at

marketplace_purchases
  id, listing_id, buyer_organization_id, buyer_user_id,
  price_paid_cents, stripe_payment_intent_id, granted_at, status
```

### Endpoints
```
GET  /api/marketplace                          — public browse
GET  /api/marketplace/{listing_id}             — public detail + sample
POST /api/admin/marketplace/listings           — list one of your courses
DELETE /api/admin/marketplace/listings/{id}    — unlist
POST /api/marketplace/{listing_id}/purchase    — Stripe checkout for buyer's org
GET  /api/admin/marketplace/sales              — my seller dashboard
GET  /api/admin/marketplace/purchases          — my buyer dashboard
```

### Flow
1. Seller admin selects a course → sets price → publishes to marketplace.
2. Buyer browses public catalog (SEO-friendly `/marketplace/{slug}` pages) → previews sample slides.
3. Purchase kicks off Stripe checkout with `application_fee` (IFPI takes 10%) using `stripe.checkout.Session.create` with `transfer_data`.
4. On webhook success, we deep-copy the course into the buyer's org (respecting slide versioning).

### Watch out for
- Course versioning: buyer gets a **snapshot** at purchase time, NOT a live subscription. Seller updates don't propagate.
- IP / DMCA: need a takedown request endpoint + `is_active=false` toggle for admins.
- SCORM export in bought courses: pass through the `xapi_secret`.

---

## 3. Live Sessions (P2 · est. 5-7 days)

### Value
Turn courses from async-only into hybrid programmes. Instructor-led live sessions with attendance tracking, integrated into learning paths.

### Tables
```
live_sessions
  id, organization_id, course_id (optional), title, instructor_user_id,
  starts_at, duration_minutes, video_url (Zoom/Meet/self-hosted),
  max_seats, is_recorded, recording_url, created_at

live_session_registrations
  id, session_id, user_id, registered_at, attended (bool),
  attendance_marked_at, attendance_source (auto|manual)

live_session_reminders
  id, session_id, user_id, remind_at, sent_at
```

### Endpoints
```
GET  /api/live-sessions                        — list upcoming (org-scoped)
POST /api/admin/live-sessions                  — create session
POST /api/live-sessions/{id}/register          — learner registers
POST /api/admin/live-sessions/{id}/mark-attended (user_ids: [])
GET  /api/admin/live-sessions/{id}/attendance
POST /api/live-sessions/{id}/join              — issues one-time URL, records attendance
```

### Flow
1. Instructor creates session with an external video URL (Zoom/Meet).
2. Learners register → outbox queues a reminder email at `starts_at - 24h` and `- 10min`.
3. Learner clicks "Join" → we record attendance + redirect. Session becomes visible in learning path completion tracking.
4. Optional: auto-record via Zoom webhook, drop URL back into the session row.

### Watch out for
- Timezone hell: store UTC, render locale on client. Use `dayjs` (already in package.json).
- Integration boundary: DON'T try to be a video host. Trust external providers.
- Cohort visibility: only registered learners see the join URL.

---

## 4. pgvector Migration to Postgres (P2 · est. 5-8 days)

### Motivation
Unlocks the full Kimi AI Tutor plan (proper per-course embeddings, LLM re-ranking at scale). Current SQLite + JSON-column embeddings will melt above ~5000 chunks.

### Migration plan
1. **Provision Postgres** in K8s (existing Bitnami helm chart, ~1h).
2. **Install pgvector extension** — one `CREATE EXTENSION` in an alembic migration.
3. **Rewrite SourceChunk.embedding** from `JSON` → `Vector(1536)`. Requires a data migration script that:
   - Reads the JSON list from SQLite dump.
   - Re-inserts as `vector` type into Postgres.
   - Handles chunks with `embedding=None` gracefully.
4. **Swap embedding_service.semantic_search** to use pgvector's `<=>` operator (cosine distance) instead of Python-side dot-product loop.
5. **Add ANN index** — `CREATE INDEX ON source_chunks USING hnsw (embedding vector_cosine_ops);` after backfill.
6. **Test suite migration**: 25% of tests use `sqlite:///./test.db` — swap to `postgresql://` via env override. Use `pytest-postgresql` for CI.

### Deployment
- Both DBs run in parallel during cutover (dual-write for 1 week).
- Feature flag `use_pgvector` (already in KNOWN_FLAGS as "n/a" — activate) controls read path.

### Watch out for
- SQLAlchemy version: pgvector needs 2.0+ (we're on 2.0 already ✅).
- Fernet-encrypted columns: no change (bytes column type).
- Backup / restore story is different — RDS snapshots vs SQLite file copy.
- `has_table` inspector calls in alembic migrations may behave differently.

### Post-migration wins available
- Real semantic search across ALL courses in an org (not just per-course).
- LLM re-ranking (Kimi's `tutor_reranker`) becomes viable.
- New endpoint: `/api/authoring/deep-search` — natural-language search across a corpus. Uses pgvector + LLM in one call.

---

## Session pickup order (recommended)

If a next agent has 1 session, pick **one** feature. Suggested priority:
1. **Affiliate program** — smallest, real revenue impact, safe integration surface.
2. **Live sessions** — biggest UX win, but external-video integration is risky.
3. **Marketplace** — highest revenue potential but Stripe payouts add tax/legal complexity.
4. **pgvector migration** — infra work; wait until you have >2500 chunks to make it worth the migration cost.
