# Agent Workflow — Invariants

Rules the E1 agent MUST follow on every session in this codebase. If a
handoff summary contradicts a rule here, this file wins.

---

## Before calling `finish` — ALWAYS run pre-finish check

Whenever a work batch is complete and about to hand off (via `finish`),
run:

```bash
python /app/backend/scripts/pre_finish_check.py
```

This performs four checks in sequence:

1. Regenerates docs (`build_docs.py`) — mutates on-disk manuals to
   match current `app.routes` / models / routers.
2. Verifies no drift remains (`build_docs.py --check` exits 0).
3. Runs endpoint signature + decorator lints (catches ForwardRef leaks).
4. Runs `pytest tests/test_docs_completeness.py`.

If this exits 0 → safe to `finish`.
If it exits 1 → STOP. Fix what it flagged before touching `finish`.

### Why this is a hard rule

Between Iter 38 and Iter 39, five route-adding iterations regenerated
docs at different points, but the final "Save to GitHub" caught a
snapshot in-between. GitHub CI failed with 95 undocumented routes.
The fix is trivial (regen + commit), but only visible AFTER a
push→CI round-trip. Running `pre_finish_check.py` before every
finish guarantees the drift is caught locally.

## After adding a new API route

Same drill: `pre_finish_check.py` will catch missing docs. Don't rely
on the CI feedback loop.

## After adding a new decorator in `services/` or `core/`

If it uses `functools.wraps` and might be applied to a FastAPI
endpoint, ensure the module imports `Request`, `Response`, and
`BackgroundTasks` at module scope. The `--check-decorators` pass
warns on missing imports; the endpoint-signatures pass fails the
build if any of those types leaks as a ForwardRef.

## Auth credentials

If you create/modify test/admin credentials, update
`/app/memory/test_credentials.md` immediately. Any testing agent
invocation reads it and expects current values.
