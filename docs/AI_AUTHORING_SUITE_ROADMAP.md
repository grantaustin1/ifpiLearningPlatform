# IFPI AI Authoring Suite — Implementation Spec & Roadmap
_Owner: IFPI product · Handoff to: Emergent engineering · Version: 1.0 · Date: Feb 2026_

> Master spec for the 7 AI-powered authoring features IFPI wants to layer on top
> of the existing LMS. This document is the single source of truth — read
> section 2 (Access Control) FIRST, then implement features in the order in
> section 6 (Roadmap).

---

## 1 · Executive summary

| # | Feature | Priority | Status today | Estimated build |
|---|---|---|---|---|
| 1 | Source-grounded AI tutor | 🔴 P0 | ⚠️ Naked LLM only — no RAG, no source library | ~4 days |
| 2 | Deep research | 🔴 P0 | ❌ Not built | ~3 days |
| 3 | Auto-quizzes + flashcards | 🔴 P0 | ⚠️ Quiz exists, flashcards missing | ~2 days |
| 4 | Video overviews | 🟡 P1 | ❌ Not built | ~2 days (Sora 2 wrapper) |
| 5 | TTS narration | 🟡 P1 | ❌ Not built | ~1.5 days |
| 6 | Mind maps + infographics | 🟡 P1 | ❌ Not built | ~2 days |
| 7 | Slide/PPTX export | 🟡 P1 | ❌ Not built | ~1.5 days |
| — | Podcasts / interactive audio | 🟢 P2 | **Skipped** — wrong format for IFPI's audience | — |

Total: **~16 engineering days** for the full P0+P1 suite.

### What's already in the codebase we can reuse
- `POST /api/ai/course-builder` — synchronous LLM call via `emergentintegrations.LlmChat` (Claude Sonnet default). Generates slide outlines + quiz questions from a text prompt only. **No source grounding.**
- `services/ai_builder_service.generate_course()` — the underlying helper.
- `SlideVersion` — append-only version history (Iter 19). Reuse for AI-authored slide edits.
- `services/storage_service` — pluggable storage abstraction (local + S3). Ready for large media artefacts (audio, video, PPTX).
- `ImportJob` model (Iter 16) — pattern to copy for long-running AI jobs (research runs, video generation).
- `webhook_service` (Iter 15) — fire-and-forget delivery pattern for async completion notifications.

### The Emergent LLM Key covers
- ✅ Claude Sonnet 4.6 (text generation — tutor, research, quiz, flashcard, mind-map JSON)
- ✅ Gemini Nano Banana (infographic image generation)
- ✅ GPT Image 1 (fallback / diagram generation)
- ✅ Sora 2 (video overviews)
- ✅ OpenAI TTS + Whisper (narration + eventual voice input)
- ❌ Does NOT cover: web search / research APIs (Perplexity, Tavily, SerpAPI, etc. — need dedicated key)

---

## 2 · Access control architecture — CRITICAL, READ FIRST

IFPI runs **two personas on the same platform**:

| Persona | Roles | What they see | Login flow |
|---|---|---|---|
| **IFPI staff** (course authors) | `INSTRUCTOR`, `ADMIN`, `SUPER_ADMIN` | Dashboard + `/authoring/*` AI suite + course editor | Standard email/password (or SSO) — no change |
| **Learner** | `LEARNER`, `MANAGER` (SSO'd from ERP360) | `/learn/*`, catalog, certificates, quizzes | Same auth backend — different landing page based on role |

### Rules for the AI suite (non-negotiable)
1. **Every AI-authoring endpoint** must go through the new dependency:
   ```python
   requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")
   ```
   Learners get **HTTP 403** — not a hidden nav item, an actual API refusal.

2. Add a semantic helper to `auth/dependencies.py` to make intent scannable:
   ```python
   def requires_staff() -> Callable:
       """Alias for the IFPI-team gate. Use on every /api/authoring/* route."""
       return requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN")
   ```

3. **Frontend routing:** on login, resolve `user.roles`. If `LEARNER` is the only role → redirect to `/learn`. Otherwise → `/dashboard`. The `/authoring/*` routes must be wrapped in `<Protected staffOnly>` (new prop on the existing `Protected` component).

4. **Cost containment:** each staff org gets a monthly AI budget (`Organization.ai_monthly_budget_cents`, default $50). Track spend in a new `AIUsageLedger` (see §3). Learners cannot consume budget — the gate above enforces this.

---

## 3 · Shared infrastructure (build ONCE, use everywhere)

Every AI feature below depends on these three pieces. Build them first (day 1–2 of Iter 22).

### 3.1 · Source library (`SourceDocument` model)

The "source-grounded" and "deep research" features both need a place to store per-org reference material.

```python
class SourceDocument(Base):
    __tablename__ = "source_documents"
    id                = Column(Integer, primary_key=True)
    organization_id   = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    course_id         = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)  # optional scoping
    title             = Column(String(300), nullable=False)
    source_type       = Column(String(20))    # PDF | DOCX | URL | RESEARCH_NOTE | MANUAL
    original_url      = Column(String(800))   # if scraped/uploaded from a URL
    storage_key       = Column(String(400))   # where the raw file lives (storage_service)
    extracted_text    = Column(Text)          # plain-text extraction — the RAG input
    metadata_json     = Column(JSON)          # {authors, published_date, checksum, page_count}
    chunk_count       = Column(Integer, default=0)
    embedded_at       = Column(DateTime)
    uploaded_by_id    = Column(Integer, ForeignKey("users.id"))
    created_at        = Column(DateTime, default=_utcnow, nullable=False)


class SourceChunk(Base):
    """Retrieval-ready text chunks (~800 tokens each) with vector embeddings."""
    __tablename__ = "source_chunks"
    __table_args__ = (Index("ix_chunk_doc_ord", "document_id", "chunk_index"),)
    id            = Column(Integer, primary_key=True)
    document_id   = Column(Integer, ForeignKey("source_documents.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    chunk_index   = Column(Integer, nullable=False)
    text          = Column(Text, nullable=False)
    embedding     = Column(JSON)    # list[float] — 1536 dims (OpenAI ada-2) or 768 (Gemini)
    token_count   = Column(Integer)
```

**Endpoints** (`/api/authoring/sources`, all staff-only):
- `POST /` — upload a PDF/DOCX/URL. Backend extracts text (reuse `bulk_import.py` extractors), chunks (~800 tok), embeds via Emergent LLM Key.
- `GET /` — paginated list per org, optional `course_id` filter.
- `DELETE /{id}` — cascade-deletes chunks.
- `POST /search` — semantic search (top-k chunks by cosine similarity) — internal, used by tutor + quiz.

**Embedding provider:** call integration playbook for `openai text-embedding-3-small` (cheap, fast, 1536-dim) OR reuse Nano Banana embed endpoint if bundled. Store as raw JSON list — no pgvector needed at MVP scale (< 10k chunks/org).

### 3.2 · AI job queue (`AIJob` model)

Reuse the `ImportJob` pattern for long-running features (research, video, TTS).

```python
class AIJob(Base):
    __tablename__ = "ai_jobs"
    id                = Column(Integer, primary_key=True)
    organization_id   = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id     = Column(Integer, ForeignKey("users.id"))
    job_type          = Column(String(40), nullable=False, index=True)
    #   TUTOR_ANSWER | DEEP_RESEARCH | AUTO_QUIZ | FLASHCARDS | VIDEO_OVERVIEW
    #   TTS_NARRATION | MIND_MAP | INFOGRAPHIC | PPTX_EXPORT
    status            = Column(String(20), default="PENDING", index=True)
    #   PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    input_json        = Column(JSON)     # user's request
    output_json       = Column(JSON)     # LLM response / artefact refs
    artefact_url      = Column(String(600))    # when the output is a file (mp4, mp3, pptx, png)
    cost_cents        = Column(Integer, default=0)
    error_log         = Column(Text)
    started_at        = Column(DateTime)
    completed_at      = Column(DateTime)
    created_at        = Column(DateTime, default=_utcnow, nullable=False)
```

Reuse `apscheduler` (already installed). Add a background worker `services/ai_worker.py` that polls `AIJob.status='PENDING'` every 5 s and dispatches per `job_type`.

### 3.3 · AI usage ledger (spend control)

```python
class AIUsageLedger(Base):
    __tablename__ = "ai_usage_ledger"
    __table_args__ = (Index("ix_ai_usage_org_month", "organization_id", "billing_month"),)
    id                = Column(Integer, primary_key=True)
    organization_id   = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"))
    job_id            = Column(Integer, ForeignKey("ai_jobs.id"), nullable=True)
    provider          = Column(String(30))    # claude | openai | gemini | sora | tts
    model             = Column(String(60))
    input_tokens      = Column(Integer)
    output_tokens     = Column(Integer)
    cost_cents        = Column(Integer)
    billing_month     = Column(String(7))     # "2026-02"
    created_at        = Column(DateTime, default=_utcnow, nullable=False)
```

Before every LLM call, check `sum(cost_cents WHERE org+month) < ai_monthly_budget_cents`. If over → return HTTP 429 + a friendly upgrade nudge.

Add `ai_monthly_budget_cents INTEGER DEFAULT 5000` to `organizations` in the same Alembic revision.

---

## 4 · Feature specs

### FEATURE 1 — Source-grounded AI tutor 🔴 P0

**What it does:** An in-editor chat panel where an IFPI author asks questions like *"Summarise chapter 3 in 5 bullets suitable for a slide"* or *"What's the ISO 27001 requirement on password rotation?"*. Answers are **grounded** in the org's uploaded source documents (§3.1) with visible citations.

**Why P0:** Without this, generated content is unaccountable and can hallucinate IFPI-specific policy. This is the credibility foundation of the whole suite.

**Data:** No new tables — uses `SourceDocument` + `SourceChunk` from §3.1. Add optional `TutorSession` for multi-turn context:
```python
class TutorSession(Base):
    __tablename__ = "tutor_sessions"
    id, organization_id, user_id, course_id (nullable),
    messages_json = Column(JSON),   # [{role, content, citations: [chunk_ids]}]
    started_at, last_message_at
```

**Endpoints** (staff-only):
- `POST /api/authoring/tutor/ask` — body: `{session_id?, question, course_id?, max_sources: 5}`. Runs: (a) embed the question, (b) top-k retrieve chunks from `SourceChunk`, (c) build prompt with `SYSTEM: You are IFPI's course-authoring assistant. Answer using ONLY the provided sources. Cite [S1], [S2] inline.`, (d) call Claude Sonnet via `emergentintegrations`, (e) return `{answer, citations: [{chunk_id, doc_title, page}]}`.
- `GET /api/authoring/tutor/sessions` — recent sessions.
- `POST /api/authoring/tutor/sessions/{id}/save-as-slide` — one-click: convert a tutor answer into a new draft slide on the current course.

**Frontend UX:**
- Right-side drawer on `CourseEditPage` (`/authoring/course/{id}`).
- Message list with citation chips `[S1]` that expand to a preview of the source chunk.
- "Insert as slide" button on any answer.
- Non-negotiable: **staff-only** wrapper.

**Acceptance criteria:**
- Asking a question with no sources uploaded returns "No sources available — upload one first" (never a hallucinated answer).
- Every answer has ≥ 1 citation OR an explicit "no sources match" refusal.
- Test: upload a PDF containing "the answer is Zurich", ask an unrelated question → assistant refuses cleanly.

**Integrations to open playbooks for:**
- `integration_playbook_expert_v2("Claude Sonnet 4.6 text with source-grounding")` — for the LLM call
- `integration_playbook_expert_v2("OpenAI text-embedding-3-small for semantic retrieval")` — for embeddings

---

### FEATURE 2 — Deep research 🔴 P0

**What it does:** Staff clicks "Research this topic" and enters a query. Backend fires up a multi-step research agent that: (a) searches the web via a research API, (b) scrapes top results, (c) synthesises a briefing document, (d) saves it as a new `SourceDocument` with `source_type='RESEARCH_NOTE'`. That doc becomes tutor-groundable immediately.

**Why P0:** Keeps course content current. Cybersecurity / compliance training decays fast — without this, courses are stale within 6 months.

**Data:** No new tables. Uses `AIJob` (job_type=`DEEP_RESEARCH`) + creates a `SourceDocument`.

**Endpoints** (staff-only):
- `POST /api/authoring/research/start` — body: `{query, depth: "quick"|"deep", course_id?}`. Returns `{job_id, status: "PENDING"}`.
- `GET /api/authoring/research/{job_id}` — poll status.
- Job worker: dispatches to `services/deep_research_service.py` which:
  1. Web search (Tavily or Perplexity API) — get top 10 URLs
  2. Scrape each URL (reuse `web_search_tool` playbook)
  3. Filter for domain trust (config'd whitelist per org)
  4. Chunk + summarise each with Claude Sonnet
  5. Cross-reference + de-duplicate claims
  6. Write final briefing (2-4k words) with inline citations
  7. Create `SourceDocument` + chunks + embeddings
  8. Notify author via in-app notification

**Frontend UX:**
- New page `/authoring/research` — form + list of past runs.
- Live status polling with %-complete + current step ("Scraping brookings.edu...").
- On completion → auto-open the resulting SourceDocument in the tutor drawer.

**Acceptance criteria:**
- `quick` mode returns in ≤ 90 s. `deep` mode ≤ 6 min.
- Every claim in the briefing has a citation footnote.
- Whitelist/blacklist per-org domain filter is respected.
- Cost per `deep` run ≤ $0.80 (tracked in ledger).

**Integrations to open playbooks for:**
- `integration_playbook_expert_v2("Tavily search API for research agents")` — recommended provider
- Alternative: `integration_playbook_expert_v2("Perplexity API sonar-pro deep research")`
- **Requires user to supply an API key** — not in the Emergent LLM key. Env var: `RESEARCH_API_KEY`.

---

### FEATURE 3 — Auto-quizzes + flashcards 🔴 P0

**What it does:**
- **Auto-quizzes** — pick any subset of course slides + click "Generate quiz". LLM produces MCQ/T-F/short-answer questions grounded in slide content. Author reviews, edits, publishes.
- **Flashcards** — from any slide or research doc, generate spaced-repetition ready cards (front/back). Learners see these in `/learn/{course}/flashcards`. **(Learner-side rendering: read-only, no authoring)**.

**Status today:** `POST /api/ai/course-builder` includes basic quiz gen but not scoped to specific slides, not editable in a review UI, and not flashcards.

**Data:**
```python
class Flashcard(Base):
    __tablename__ = "flashcards"
    id, course_id, slide_id (nullable), organization_id
    front = Column(String(500), nullable=False)
    back  = Column(Text, nullable=False)
    hint  = Column(String(300))
    difficulty = Column(Integer, default=2)   # 1-easy .. 5-hard
    tags  = Column(JSON)   # list[str]
    generated_by_ai = Column(Boolean, default=True)
    source_chunk_ids = Column(JSON)   # provenance for grounded generation
    created_by_id, created_at

class FlashcardReview(Base):
    """Learner-side SM-2 spaced repetition state — read-write for LEARNER role."""
    __tablename__ = "flashcard_reviews"
    id, user_id, flashcard_id
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    next_review_at = Column(DateTime, index=True)
    last_reviewed_at, review_count
```

**Endpoints:**

Staff-only authoring:
- `POST /api/authoring/quiz/generate` — `{course_id, slide_ids: [], num_questions, difficulty, use_sources: true}`. Returns draft questions.
- `POST /api/authoring/quiz/publish` — commits reviewed questions into an existing or new `Exam`.
- `POST /api/authoring/flashcards/generate` — `{course_id, slide_ids?, source_document_ids?, count}`. Returns draft cards.
- `POST /api/authoring/flashcards/bulk-save` — commits reviewed cards.
- `GET/PATCH/DELETE /api/authoring/flashcards/{id}` — CRUD.

Learner-facing (existing `LEARNER` role):
- `GET /api/learn/courses/{course_id}/flashcards/due` — cards due for review today.
- `POST /api/learn/flashcards/{card_id}/review` — `{quality: 0-5}` — updates SM-2 state.

**Frontend UX:**
- On `CourseEditPage`: "Generate flashcards from selected slides" bulk action → review table → "Save all N cards".
- On learner side: new `/learn/{course}/flashcards` page — swipeable card stack, keyboard 1-5 quality rating.

**Acceptance criteria:**
- Generated cards cite source_chunk_ids (grounded, no hallucination).
- SM-2 algorithm correctly schedules next review (verified via unit test with 10 known-input reviews).
- Learner cannot access authoring endpoints (403).

---

### FEATURE 4 — Video overviews 🟡 P1

**What it does:** Author clicks "Generate 60-second overview video" on a course. Backend: (a) builds a script from the course summary, (b) generates video via Sora 2, (c) generates matching TTS narration (feature 5), (d) muxes them, (e) stores the mp4, (f) creates a `SlideType.VIDEO` slide at the top of the course.

**Data:** Uses `AIJob` (job_type=`VIDEO_OVERVIEW`) + storage_service for the mp4.

**Endpoints** (staff-only):
- `POST /api/authoring/video/generate-overview` — `{course_id, style: "explainer"|"documentary"|"cinematic", duration_seconds: 60, voice: "alloy"|"echo"|"nova"}`. Returns `{job_id}`.
- `GET /api/authoring/video/{job_id}` — poll status.
- On completion → auto-attach the video URL as a new introductory slide (position 0).

**Frontend UX:**
- Big "Generate overview video" CTA on the course editor.
- Preview player embedded once ready.
- Regenerate button (costs another credit).

**Acceptance criteria:**
- End-to-end runtime ≤ 4 minutes for 60-second clips.
- Cost tracked and enforced against budget.
- Failed generations don't leave orphan slides.

**Integrations to open playbook for:**
- `integration_playbook_expert_v2("Sora 2 video generation via Emergent LLM key")`
- `integration_playbook_expert_v2("OpenAI TTS Emergent LLM key")` — for the narration overlay

---

### FEATURE 5 — TTS narration 🟡 P1

**What it does:** For any TEXT slide, click "Narrate this slide" → generates an .mp3 attached to the slide. Learners get a play button on the slide during `/learn/*`.

**Data:** New column on `CourseSlide`: `narration_audio_url` (String(500), nullable). Reuse storage_service.

**Endpoints** (staff-only):
- `POST /api/authoring/tts/narrate-slide` — `{slide_id, voice, speed: 1.0, model: "tts-1-hd"}`. Sync call (~15 s for a 200-word slide). Returns `{audio_url}`.
- `POST /api/authoring/tts/narrate-course` — bulk narrate every slide in a course. Async → `AIJob`.

**Frontend UX:**
- "Narrate" pill button on each slide in the editor.
- Learner `LearnPage` shows an audio scrubber on slides that have `narration_audio_url`.

**Acceptance criteria:**
- Voice + speed persist per-org preference.
- Skipping narration is possible for a learner (audio is opt-in).

**Integrations:**
- `integration_playbook_expert_v2("OpenAI TTS Emergent LLM key")`

---

### FEATURE 6 — Mind maps + infographics 🟡 P1

**What it does:** Two related generators:
- **Mind map** — from a course or research doc, LLM produces a hierarchical JSON tree (Markmap format). Renders in-browser via markmap-lib.
- **Infographic** — LLM writes a visual prompt describing the course's key stats → Nano Banana produces a shareable PNG.

**Data:**
```python
class VisualArtefact(Base):
    __tablename__ = "visual_artefacts"
    id, organization_id, course_id (nullable), source_document_id (nullable)
    kind = Column(String(20))   # MINDMAP | INFOGRAPHIC | DIAGRAM
    title
    payload_json  = Column(JSON)    # Markmap tree for mindmaps
    image_url     = Column(String(500))  # for infographics
    prompt_used   = Column(Text)
    created_by_id, created_at
```

**Endpoints** (staff-only):
- `POST /api/authoring/visuals/mindmap` — `{course_id | source_document_id, depth: 3}`. Returns Markmap JSON.
- `POST /api/authoring/visuals/infographic` — `{course_id, style, aspect_ratio: "1:1"|"16:9"}`. Async → `AIJob`.
- `GET /api/authoring/visuals?course_id=` — list.

**Frontend UX:**
- New tab on the course editor: "Visuals" — list + generate button + inline preview.
- Mind map: interactive markmap-lib component with export-to-PNG.
- Infographic: click to download or "insert as slide".

**Acceptance criteria:**
- Mind maps render at depth 3 with no truncation.
- Infographic prompt includes IFPI's brand colours (from `Organization.theme_json`).

**Integrations:**
- `integration_playbook_expert_v2("Gemini Nano Banana image generation")`
- Frontend: `yarn add markmap-lib markmap-view` (MIT, ~40kb gzipped)

---

### FEATURE 7 — Slide / PPTX export 🟡 P1

**What it does:** From any course, click "Export as PowerPoint" → generates a .pptx with each `CourseSlide` mapped to a slide (media placeholders + text + brand template).

**Data:** None. Purely an export job.

**Endpoints** (staff-only):
- `POST /api/authoring/export/pptx` — `{course_id, template: "ifpi-brand"|"minimal"|"academic"}`. Sync ok (~4 s for 30 slides). Returns `{download_url}`.
- Uses `python-pptx` (pure Python, no external service).

**Frontend UX:**
- "Export → PowerPoint" in the course editor top bar.
- Instant download once ready.

**Acceptance criteria:**
- Media slides embed the video/image, not just a link.
- Text slides preserve heading hierarchy.
- Deck opens without errors in Keynote + PowerPoint + LibreOffice Impress.

**Integrations:** None external. Just `pip install python-pptx==0.6.23` (add to requirements.txt).

---

## 5 · Cross-cutting non-functional requirements

1. **Rate limiting.** Every `/api/authoring/*` route: 20 req/min per user, 200/min per org. Use `slowapi`.
2. **Audit logging.** Every AI job creates an `AuditLog` row with `action="AI_JOB_STARTED"` and `metadata_json` containing input digest + cost estimate.
3. **Feature flags.** `Organization` gains `feature_flags JSON`. Toggle each feature per-org so IFPI can beta-test with select tenants.
4. **Idempotency.** All `POST /generate` endpoints accept `Idempotency-Key` header — retries within 24h return the cached result.
5. **Redaction.** Before any prompt goes to a third-party LLM, run PII redaction on user input (emails, ID numbers). Add `services/pii_redactor.py`.
6. **Observability.** Structured logs `{event, job_id, org_id, user_id, provider, model, duration_ms, cost_cents}` — pipe to stdout in JSON so Emergent's log pipeline can index them.

---

## 6 · Recommended build sequence (roadmap)

### Iter 22 — Foundation (4 days)
- [ ] `SourceDocument` + `SourceChunk` model + Alembic migration
- [ ] `AIJob` model + background worker (`services/ai_worker.py`)
- [ ] `AIUsageLedger` + `Organization.ai_monthly_budget_cents` + budget-gate helper
- [ ] `auth.dependencies.requires_staff()` semantic alias
- [ ] `Protected staffOnly` prop on the frontend + role-based landing-page redirect
- [ ] PII redactor + rate limiter middleware
- [ ] Regression: full Iter 14-21 suite still green

### Iter 23 — Feature 1 (source-grounded tutor) (4 days)
- [ ] Source upload router (PDF/DOCX/URL → text extract → chunk → embed)
- [ ] Semantic search endpoint
- [ ] Tutor router + session model
- [ ] Tutor drawer UI on CourseEditPage
- [ ] Golden-set tests: 10 questions with known-correct citations

### Iter 24 — Feature 2 (deep research) (3 days)
- [ ] Research service + Tavily/Perplexity playbook integration
- [ ] Whitelist config per org
- [ ] Research runs page
- [ ] Requires user-supplied `RESEARCH_API_KEY`

### Iter 25 — Feature 3 (quiz + flashcards) (2 days)
- [ ] Flashcard + FlashcardReview models
- [ ] Grounded quiz generation from selected slides
- [ ] Learner-side spaced-repetition player
- [ ] SM-2 unit tests

### Iter 26 — Features 4 + 5 (video + TTS) (3.5 days)
- [ ] Sora 2 wrapper + AIJob dispatch
- [ ] TTS wrapper + `CourseSlide.narration_audio_url`
- [ ] Video overview button on course editor
- [ ] Learner audio scrubber

### Iter 27 — Features 6 + 7 (visuals + export) (3.5 days)
- [ ] `VisualArtefact` model + mind-map generator + Nano Banana infographic generator
- [ ] `python-pptx` export with brand template
- [ ] Visuals tab on course editor

---

## 7 · Definition of Done (per feature)

For each feature above, "shipped" means ALL of:
1. ✅ Alembic migration merged
2. ✅ Backend endpoints tested via `testing_agent_v3_fork` (not curl-only)
3. ✅ Frontend UI has `data-testid` attributes on every interactive element
4. ✅ Learner role is provably blocked (403 test case)
5. ✅ Cost is tracked in `AIUsageLedger` and enforced against org budget
6. ✅ Rate limit applied
7. ✅ PRD.md updated
8. ✅ Feature flag defaults OFF; enabled per-org via admin API

---

## 8 · Product owner decisions (locked in Feb 2026)

1. **Research API:** ✅ **Tavily** (~$0.08/deep-search, faster than Perplexity for our depth). Requires user-supplied `TAVILY_API_KEY` env var.
2. **Video provider:** ✅ **Sora 2** via Emergent LLM Key. **Per-org monthly cap: $200** (~400 seconds of video/month at ~$0.50/min). Enforced via `AIUsageLedger` before every Sora dispatch.
3. **Flashcards learner UX:** ✅ **Full SM-2 spaced-repetition** — daily due queue + 0-5 quality rating, next-review scheduling per learner.
4. **Brand assets:** ✅ **IFPI logo uploaded** at `/app/backend/assets/ifpi_logo.png` + served at `/uploads/ifpi_brand_logo.png`. Org id=1 configured with:
   - `logo_url = "/uploads/ifpi_brand_logo.png"`
   - `primary_color = "#262262"` (deep navy from wordmark)
   - `cert_accent_color = "#F5A500"` (gradient underline midpoint)
   - PPTX exports + AI-generated infographics + mind maps will pull these values automatically. A full `.pptx` brand master can be dropped in later at `/app/backend/assets/ifpi_brand_master.pptx` for tighter design control.
5. **PII redaction:** ✅ **Option (b) — redact by default, staff can toggle off per-question.**
   - Default behaviour on every `/api/authoring/tutor/ask` + related endpoint: run `services/pii_redactor.py` over the incoming prompt AND retrieved chunks. Replace emails, names, IDs with `<learner_N>` placeholders. Send to LLM. When response comes back, un-redact for the *staff viewer* (so they see real names in the UI) but keep the LLM prompt/response pair in the audit log with redacted form.
   - Per-question override: request payload gains `pii_redact: bool = True`. Setting to `false` requires the caller to have `ADMIN` or `SUPER_ADMIN` role (not INSTRUCTOR) AND writes an `AuditLog` entry with `action="AI_PII_REDACT_DISABLED"` for compliance.
   - Every response includes `redaction_applied: bool` so the UI can display a "PII redacted" chip.

---

_End of spec — hand this file to the implementing agent verbatim._
