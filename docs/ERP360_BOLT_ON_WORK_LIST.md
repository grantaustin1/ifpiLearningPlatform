# ERP360 ↔ IFPI Integration — Local Compliance Delta

> **📌 Canonical contract:** `/app/docs/IFPI_INTEGRATION_HANDOFF.md` (§1–§7). Mirrored verbatim from the ERP360-side single-source-of-truth. **All contract questions resolve there.** This document tracks *only* IFPI's compliance state against that spec — no re-derivation, no parallel vocabulary.

## Compliance status (updated 2026-02-12, Iter 35)

| Spec § | Item | Status | IFPI code path |
|---|---|---|---|
| §1 | SSO exchange (JSON binding) | ✅ shipped | `routers/auth.py::sso_exchange` |
| §1 | HS256 verify, `iss=erp360`, `aud=ifpi-lms`, jti replay | ✅ shipped | `services/sso_service.py::verify_inbound_token` + `_check_replay` |
| §1 | `iat` freshness (≤5 min) | ✅ shipped | `MAX_TOKEN_AGE_SECONDS = 300` |
| §1.1 | Form-POST binding (`Content-Type: application/x-www-form-urlencoded` → 303) | ✅ shipped Iter 35 | `routers/auth.py::sso_exchange` (Content-Type branch) |
| §1.1 | `return_to` same-origin allowlist (must start `/`, not `//`) | ✅ shipped | same |
| §2 | HMAC-SHA256 raw-body verification via `X-ERP360-Signature: sha256=<hex>` | ✅ shipped | `routers/erp360_sync.py::_verify_signature` |
| §2 | Idempotency on `X-ERP360-Event-Id` | ✅ shipped | `_SEEN_EVENT_IDS` (in-mem; TODO: move to SQL like `sso_jti_seen` for multi-replica) |
| §2 | 2xx within 10s + supports re-delivery | ✅ shipped | route returns 202 with no long-running work inside |
| §2 | `user_deactivated` handler (revoke access) | ✅ shipped | `routers/erp360_sync.py` `is_active = False` |
| §3 | Env vars `ERP360_SSO_SHARED_SECRET`, `IFPI_WEBHOOK_OUTBOUND_SECRET` | ✅ configured | `backend/.env` + `core/config.py` |
| §4 | `GET /api/erp360/sync/status` | ✅ shipped | `routers/erp360_sync.py::erp360_sync_status` |
| §4 | `POST /api/erp360/sync/test-ping` | ✅ shipped (admin-gated) | `routers/erp360_sync.py::erp360_sync_test_ping` |
| §4 | Outbound webhooks IFPI → ERP360 (`learner.invited`, `enrollment.completed`, `certificate.issued`, `ai.spend.threshold`, `course.published`) | ⏳ not started | future — sender/dispatcher not yet built |
| §4 | `IFPI_API_TOKEN` server-to-server bearer (scoped) | ✅ shipped (mint via `/api/admin/api-tokens`) | `models/api_token.py` + admin router |
| §6.1 | Dedup/join on `user.sub` (never on email) | ✅ shipped | `services/sso_service.py::jit_provision` first checks `erp360_user_id == sub`, email is fallback only |
| §6.2 | Role vocabulary: OWNER, MANAGER, ACCOUNTANT, HEAD_OF_ADMIN, FRONT_DESK, SALES, TRAINER, HR_ADMIN, HR_MANAGER, RSM, VIEWER | ✅ shipped | `services/sso_service.py::ERP360_TO_IFPI_ROLE` — unmapped names coerce to LEARNER via `.get(key, "LEARNER")` |
| §6.2 | Unknown-role coerce → LEARNER + warn-log | ✅ shipped | `routers/erp360_sync.py::_replace_erp360_roles` warn-logs unmapped names |
| §6.2 | `data.new_roles` object shape `{role_name, scope, branch_id}` unpacked; `scope`/`branch_id` accept-and-ignore v1 | ✅ shipped Iter 35 | `routers/erp360_sync.py::_extract_role_names` — raw shape preserved in audit_metadata |
| §6.3 | HMAC signing spec (raw body bytes, `sha256=<hex>`) | ✅ shipped | `_verify_signature` |
| §6.3 | Replay window `X-ERP360-Timestamp` ±5 min | ⏳ header ignored on inbound today; MAY per spec (dedupe on `event_id` mandatory and shipped) | future — cheap add when we tighten |
| §6.4 | Accept re-delivered payloads (ERP360 re-signs from current env every attempt) | ✅ shipped (idempotency handles this) | `_SEEN_EVENT_IDS` |
| §6.5 | `SameSite=None; Secure` on cookies + explicit `ALLOWED_ORIGINS` list | ✅ shipped | `AUTH_COOKIE_SAMESITE=none`, `AUTH_COOKIE_SECURE=true`, deploy-surface `CORS_ORIGINS` reads through `core/config.py` |
| §7.1 | Billing abstraction (per-org `billing_mode`, `Entitlement` intermediate) | ⏳ not started | next chunk of IFPI work |
| §7.2 | `users.erp360_user_id` + `persons.erp360_person_id` columns | ✅ shipped | `models/identity.py` |
| §7.2 | Verified-email-only link on first SSO for previously-native user | ⏳ email match is any-email today, not `email_verified_at IS NOT NULL` | small tightening in `SSOService.jit_provision` |
| §7.3 | Scoped role rewrite (only `source='erp360'` rows wiped; IFPI-native survives) | ✅ shipped Iter 35 | `user_roles.source` column + scoped DELETE in `_replace_erp360_roles` AND `SSOService.jit_provision` |
| §7.4 | Per-org connection state (`organizations.integrations` JSONB) | ⏳ global `SSO_ENABLED` still in use | next chunk of IFPI work |
| §7.4 | `user_deactivated`/`role_changed` only match users in payload's `org_slug` | ⏳ currently matches globally by `erp360_user_id`/email | tighten alongside §7.4 |

## Legend
- ✅ Shipped and tested (regression tests in `backend/tests/test_iteration35_erp360_scoped_roles_and_form_post.py` and iter14/iter17 SSO suites).
- ⏳ Known gap — tracked here to prevent silent drift from spec.

## What's next
Priority order for the next IFPI work chunk:
1. **§7.4 per-org connection state** — retire global `SSO_ENABLED`; scope handlers to payload's `org_slug`. Blocks multi-tenant prod.
2. **§7.1 entitlement abstraction** — must land BEFORE any Stripe P1 work, or that becomes rip-and-replace.
3. **§7.2 verified-email tightening** — small guard on `jit_provision` first-time link path.
4. **§6.3 replay window** — enforce ±5 min on `X-ERP360-Timestamp`.
5. **§4 outbound webhooks** — IFPI → ERP360 dispatcher (`learner.invited`, `enrollment.completed`, `certificate.issued`).
6. **`/api/v1/` versioning namespace** — keep unversioned aliases ≥1 sprint.
