# Resume IFPI Build — Quick Reference

**Last session ended:** 2026-02-08 after iteration 11.
**Last alembic head:** `b3d8915cef27`
**Test state:** 39/39 pytest across iter9+10+11 ✅ · agent 007 9/9 ✅ · agent 008 18/18 ✅ · frontend 100%

---

## Pick this up next session — pasted backlog (in priority order)

### P2 — Storage
- Provision a real S3 / R2 / GCS bucket. Pure env-var flip:
  `STORAGE_BACKEND=s3` + `S3_BUCKET=...` + AWS creds. Zero code change.

### P3 — Polish & Reporting
- Schedule the AI audit digest as a weekly email to all admins (currently UI-only on `/audit`).
- AI quiz: pre-fetch cost estimate from LLM provider before kicking off a large batch.
- Cohort CSV: add badge breakdown columns + per-learner completion percentage.
- `/audit` row drill-down: clicking a row opens a side panel with full JSON metadata + linked target.

### Pending Improvement Suggestion (proposed at end of iter 11, not yet approved)
- **Open Badges 3.0 / W3C Verifiable Credentials** on issued certificates — QR code linking
  to the existing public `/verify/<token>` page, plus a JSON-LD VC payload so other LMSes
  can ingest IFPI completions as portable credentials. Turns IFPI certs into transferrable,
  HR-ingestable credentials (BPI/RIAA/Recording Academy recognition surface).

### Deliberately deferred
- ERP360 SSO bridge — opt-in via `SSO_ENABLED=true`. IFPI runs standalone forever.
- ERP360 webhook receiver — code at `/app/docs/ERP360_INTEGRATION.md` (ready for ERP360 team).

---

## Restart command for the next agent

> "Resume IFPI from `/app/memory/PRD.md` and `/app/memory/RESUME_HERE.md`.
>  Run agent 007 and agent 008 first to confirm health, then ask me which
>  backlog item to tackle next."
