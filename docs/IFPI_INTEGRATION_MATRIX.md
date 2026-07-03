# IFPI ↔ ERP360 Integration Matrix

> **The contract that lets IFPI run either as a stand-alone SaaS or as a sibling module inside the ERP360 platform, without code branches.**

## 1. Modes at a glance

| Mode | Configuration | Auth Flow | Billing | User Directory |
|---|---|---|---|---|
| **Stand-alone (default)** | `SSO_ENABLED=false` | Local password + JWT | IFPI's own Stripe integration (backlog) | Local `users` table only |
| **Sibling (ERP360-embedded)** | `SSO_ENABLED=true` + `ERP360_SSO_SHARED_SECRET=<hmac>` | HS256 handoff on every SSO click | Delegates to ERP360 lite-billing (env-gated) | JIT-provisioned from ERP360 identity |

## 2. Toggle points

Every integration point is **feature-flagged** in `.env` — no code changes needed to flip modes.

| Flag | Default | Effect when TRUE |
|---|---|---|
| `SSO_ENABLED` | `false` | Enables `/api/auth/sso-exchange`, hides "Register" from login page |
| `SSO_ISSUER` | `erp360` | Expected `iss` claim on inbound SSO JWT |
| `SSO_AUDIENCE` | `ifpi-lms` | Expected `aud` claim |
| `SSO_ROLE_MAP_JSON` | see below | Overrides default role mapping (TRAINER→INSTRUCTOR etc.) |
| `ERP360_BILLING_BASE_URL` | *(unset)* | If set, IFPI checkout redirects to ERP360's payment flow |
| `ERP360_WEBHOOK_INBOUND_SECRET` | *(unset)* | If set, IFPI accepts `/api/erp360/webhooks/*` events from ERP360 |
| `WEBHOOK_OUTBOUND_TO_ERP360_URL` | *(unset)* | If set, IFPI mirrors `learner.*` events to ERP360 |

Default role mapping (override with `SSO_ROLE_MAP_JSON`):
```json
{
  "OWNER": "ADMIN",
  "SUPER_ADMIN": "ADMIN",
  "ADMIN": "ADMIN",
  "MANAGER": "ADMIN",
  "TRAINER": "INSTRUCTOR",
  "VIEWER": "LEARNER",
  "RECEPTION": "LEARNER",
  "MEMBER": "LEARNER"
}
```

## 3. Data ownership boundaries

| Concern | Owner in stand-alone | Owner in sibling mode |
|---|---|---|
| User identity | IFPI | **ERP360** (IFPI mirrors) |
| Password | IFPI `bcrypt` | ERP360 (IFPI has no local password when SSO is on) |
| Roles | IFPI role_registry | Mapped from ERP360 on each SSO |
| Courses, slides, exams | IFPI (always) | IFPI (always) |
| Flashcards, progress | IFPI (always) | IFPI (always) |
| Certificates | IFPI (always) | IFPI (issues) + notified to ERP360 (via `certificate.issued` webhook) |
| Billing subscriptions | IFPI Stripe | ERP360 |
| AI spend & budgets | IFPI (always) | IFPI (surfaced back to ERP360 owner dashboard) |
| Audit log | IFPI (always) | IFPI + duplicated critical events into ERP360's audit stream |

## 4. Handshake contract

### 4.1 SSO JWT payload (ERP360 → IFPI)
```json
{
  "iss": "erp360",
  "aud": "ifpi-lms",
  "sub": "<erp360_user_id>",
  "email": "user@company.com",
  "name": "Full Name",
  "roles": ["TRAINER", "MANAGER"],
  "org_slug": "acme",
  "iat": 1707000000,
  "exp": 1707000060,      // <= 60 s TTL
  "jti": "<uuidv4>"        // required, single-use
}
```
Signed with the **shared HMAC-HS256 secret**. Never uses RS256 in either direction.

### 4.2 Replay protection
- Every `jti` is persisted for `exp + 300 s` in the `sso_replay_tokens` table (see `services/sso_service.py`).
- Duplicate `jti` → `401 SSO_REPLAY_DETECTED`.

### 4.3 IFPI response
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque>",
  "user": { "id": 42, "email": "...", "roles": ["INSTRUCTOR"] },
  "jit_provisioned": true
}
```

## 5. Webhooks IFPI emits to ERP360 (sibling mode)

Only when `WEBHOOK_OUTBOUND_TO_ERP360_URL` is set. Signed with `X-IFPI-Signature: sha256=<hmac>`.

| Event | Payload |
|---|---|
| `learner.invited` | `{email, cohort, invited_by_erp360_id}` |
| `enrollment.completed` | `{learner_id, course_slug, score, duration_seconds}` |
| `certificate.issued` | `{learner_id, certificate_code, course_slug, verify_url}` |
| `ai.spend.threshold` | `{org_slug, month, spend_usd, budget_usd}` |
| `course.published` | `{course_slug, version, published_by_erp360_id}` |

## 6. Webhooks IFPI accepts from ERP360 (sibling mode)

Only when `ERP360_WEBHOOK_INBOUND_SECRET` is set. Verified via HMAC.

| Event | Effect on IFPI |
|---|---|
| `user.deactivated` | Revokes IFPI JWT family; blocks new SSO exchanges |
| `user.role_changed` | Updates the ERP360→IFPI role mapping cache |
| `org.branding_changed` | Refreshes logo + primary color on next login |
| `billing.tier_downgraded` | Enforces feature caps (e.g., disables Sora video generation) |

## 7. Preserving stand-alone parity

Every sibling-mode feature has a **stand-alone fallback**:

| Sibling feature | Stand-alone fallback |
|---|---|
| SSO login | Local email+password with rate-limited brute-force protection |
| ERP360 billing | Stripe checkout embedded in IFPI (backlog `stripe.py`) |
| ERP360 branding sync | Manual upload in `Organization Settings` |
| ERP360 user provisioning | Bulk-invite CSV + JIT accept |
| ERP360 audit stream | Local audit_log + full export |

This means **you can always turn SSO off and IFPI continues to serve tenants unchanged**.

## 8. Health & sync verification

Endpoints (roles: `OWNER`+):

| Endpoint | Returns |
|---|---|
| `/api/erp360/sync/status` | `{sso: bool, last_sso: iso8601, replay_store_size: int, webhook_outbound_healthy: bool}` |
| `/api/erp360/sync/test-ping` | Fires a test outbound webhook, returns delivery result |
| `/api/erp360/sync/handshake-dry-run` | Validates a sample JWT without persisting |

## 9. Deployment topologies

### 9.1 Stand-alone (small tenant, single container)
```
[Ingress] → [FastAPI backend :8001] → [Postgres/SQLite]
                                    ↘ [Redis (rate-limit + cache bus)]
```

### 9.2 Sibling to ERP360 (shared platform)
```
[Cloudflare + ZeroTrust]
    ↓
[Shared ingress]
    ├→ ERP360 frontend  ─┐
    ├→ IFPI frontend    ─┤ same SSO cookie domain
    ↓                    ↓
[ERP360 backend] ← webhooks → [IFPI backend]
    ↓                              ↓
[Postgres/ERP360]              [Postgres/IFPI or same]
                    ↘ shared Redis (session, rate-limit, cache bus)
```

## 10. Backlog: sync features not yet built

- **Bi-directional theme sync** — currently one-way (ERP360 → IFPI via webhook)
- **Cross-app search** — one query returns hits from both ERP360 and IFPI
- **Shared feature flags** — LaunchDarkly-style, one source of truth
- **ERP360-side "IFPI training assigned" report** — surfacing IFPI cert status on ERP360's staff profile

*Owner: Platform Ops. Update whenever an integration boundary changes.*
