# ERP360 → IFPI Integration Handoff (P0 complete on ERP360 side)

> **Source of truth:** this doc is the canonical integration contract, mirrored verbatim from the ERP360-side `IFPI_INTEGRATION_HANDOFF.md`. Both sides commit to keeping this in sync — any local reasoning in `ERP360_BOLT_ON_WORK_LIST.md` is a **compliance delta only** (what IFPI has implemented against this spec). On any conflict, this doc wins.
>
> ERP360-side spec: `ERP360_BOLT_ON_WORK_LIST.md` (their repo).
> IFPI-side compliance status: `/app/docs/ERP360_BOLT_ON_WORK_LIST.md` (this repo).

Feed this to the IFPI build so it implements the receiving side of the
contracts ERP360 already ships.

## 1. SSO exchange — what IFPI must accept

ERP360 mints an **HS256 JWT** and the browser POSTs it to IFPI:

    POST {IFPI_BASE_URL}/api/auth/sso-exchange
    Content-Type: application/json
    credentials: include            # browser fetch, cookies expected back
    {"token": "<jwt>"}

JWT claims ERP360 sends (exact contract, verify ALL of these):

| Claim | Value |
|---|---|
| `iss` | `erp360` (reject anything else) |
| `aud` | `ifpi-lms` (reject anything else) |
| `sub` | ERP360 `person_id` as a **string** (falls back to user id if person link missing) |
| `email` | staff email |
| `name` | `"First Last"` |
| `roles` | sorted array of ERP360 role names, e.g. `["OWNER"]`, `["MANAGER","SALES"]` |
| `org_slug` | ERP360 org slug, e.g. `flexgym-demo` |
| `iat` / `exp` | **TTL is 60 seconds** — IFPI must tolerate small clock skew (≤10s leeway recommended) |
| `jti` | uuid4 — IFPI should track jti for single-use/replay protection |

- Signature: **HS256** with shared secret from `IFPI_SSO_SHARED_SECRET` (same value both sides; rotate every 90 days).
- On success IFPI should set its session cookie and return 2xx. The browser is then redirected by ERP360 to `{IFPI_BASE_URL}` root — so the session cookie must be enough to land the user signed in.
- On failure return non-2xx; ERP360's UI shows a friendly retry error.
- Because the exchange is a cross-origin `fetch` with `credentials: include`, IFPI needs CORS allow-origin for the ERP360 domain with `Access-Control-Allow-Credentials: true`, and its session cookie set `SameSite=None; Secure` (until both apps share an eTLD+1 — P1.3).

### 1.1 v1.1: form-POST binding (CORS-free) — SHIPPED on IFPI side

The Emergent preview ingress stamps `Access-Control-Allow-Origin: *` at the
edge, breaking credentialed fetch. Alternative (also more robust in
production): IFPI additionally accepts `application/x-www-form-urlencoded`
with field `token` on `/api/auth/sso-exchange` and responds **303 See Other →
/dashboard**. ERP360 then submits an auto-posting hidden form (top-level
navigation) instead of fetch — no preflight, no CORS, cookies are first-party
on the IFPI domain. Classic SAML/OIDC form-post binding.

**Status:** IFPI shipped in Iter 35 (2026-02-12). Optional `return_to` form
field is validated against a same-origin allowlist (must start with `/`, must
not start with `//`; anything else falls back to `/dashboard`). ERP360 tile
can flip today.

## 2. Outbound webhooks ERP360 → IFPI — what IFPI must receive

ERP360 POSTs signed events to `IFPI_WEBHOOK_OUTBOUND_URL`
(spec target: `https://<ifpi>/api/erp360/webhooks/user`).

### Request headers

    Content-Type: application/json
    X-ERP360-Signature: sha256=<hex hmac>
    X-ERP360-Event: role_changed | user_deactivated
    X-ERP360-Event-Id: <uuid4>            # idempotency key — dedupe on this
    X-ERP360-Timestamp: <ISO-8601 UTC>

### Signature verification (must match exactly)

- Algorithm: **HMAC-SHA256** over the **raw request body bytes**, hex digest, prefixed `sha256=`.
- Secret: `IFPI_WEBHOOK_OUTBOUND_SECRET` (shared value; ERP360 signs, IFPI verifies).
- The body is compact, key-sorted JSON: `json.dumps(payload, sort_keys=True, separators=(",", ":"))`. **Verify against raw bytes as received** — do not re-serialize.

### Payload shape

    {
      "event": "role_changed",
      "event_id": "3f6c9e0e-...",
      "occurred_at": "2026-06-10T11:37:08.123456+00:00",
      "org_slug": "flexgym-demo",
      "user": {
        "sub": "9",                       // same person_id as SSO `sub` — join key
        "email": "demo.sales@flexgym.com",
        "name": "Emma Sales"
      },
      "data": { ... }                     // event-specific, see below
    }

`data` per event:

- `role_changed`: `{"old_roles": [{"role_name","scope","branch_id"}...], "new_roles": [...]}`
- `user_deactivated`: `{"reason": "<human reason or 'terminated: <reason>'>"}` — IFPI should revoke the learner's access/session.

### Delivery semantics IFPI must be ready for

- Respond **2xx** to acknowledge. Anything else (or timeout >10s) counts as failure.
- ERP360 retries failures with backoff **60s, then 300s**, and dead-letters after **3 total attempts** (manual re-queue is possible from ERP360 admin, so late duplicates can arrive).
- **Idempotency is required on `X-ERP360-Event-Id`** — the same event may be delivered more than once.
- Events fire from three ERP360 flows: admin role update, admin deactivate (is_active→false), and the dual-control staff termination flow (arrives as `user_deactivated` with `reason: "terminated: ..."`).

## 3. Shared environment variables (must match on both sides)

| Variable | ERP360 role | IFPI role |
|---|---|---|
| `IFPI_SSO_SHARED_SECRET` | signs SSO JWT | verifies SSO JWT |
| `IFPI_BASE_URL` | redirect/exchange target | (its own public URL) |
| `IFPI_WEBHOOK_OUTBOUND_URL` | POST target for events | the receiver route it exposes |
| `IFPI_WEBHOOK_OUTBOUND_SECRET` | signs webhook body | verifies `X-ERP360-Signature` |

Preview values are live and paired as of 2026-07 (both preview URLs + rotated shared secrets). Production values get swapped on both sides simultaneously at cutover (see §6.5).

## 4. Not yet built on ERP360 (P1 — IFPI should still expose its side)

- **Inbound webhooks IFPI → ERP360** (`learner.invited`, `enrollment.completed`, `certificate.issued`, `ai.spend.threshold`, `course.published`) with `X-IFPI-Signature` + `event_id` header — ERP360 receiver not implemented yet; IFPI can build/queue its sender now.
- **`IFPI_API_TOKEN`** server-to-server bearer token (scopes `read:catalog, read:analytics, write:learners`) — IFPI should support minting this in its admin.
- Health checks from the work list: `GET /api/erp360/sync/status` and `POST /api/erp360/sync/test-ping` — IFPI should implement both; ERP360 will consume them.

## 5. ERP360 reference endpoints (for IFPI devs testing against us)

- `GET  /api/ifpi/status` — integration config readiness (auth required)
- `POST /api/ifpi/sso/mint` — returns `{token, exchange_url, ifpi_base_url, expires_in}`
- `GET  /api/ifpi/webhooks/deliveries` — outbound delivery log w/ status, attempts, errors
- `POST /api/ifpi/webhooks/deliveries/{id}/retry` — re-queue failed/dead-letter

Test coverage on ERP360 side: `backend/tests/test_ifpi_integration.py` (16 tests: claims contract, HMAC, retry/DLQ, enqueue hooks).

## 6. Contract addenda (agreed during cross-app smoke testing, 2026-07)

### 6.1 User identity / dedup key — CONFIRMED

- `user.sub` (SSO JWT `sub` and webhook `user.sub`) is the ERP360 **person_id** — a
  primary key that is stable for the lifetime of the person and never reused.
  **Dedup/join on `sub`, never on email** (emails can change on ERP360).

### 6.2 Role vocabulary (ERP360 → IFPI)

Roles ERP360 can emit in SSO `roles[]` and webhook `data.*_roles[].role_name`:
`OWNER, MANAGER, ACCOUNTANT, HEAD_OF_ADMIN, FRONT_DESK, SALES, TRAINER,
HR_ADMIN, HR_MANAGER, RSM, VIEWER` (HR/RSM/VIEWER are org-optional; new roles
may be added over time).

**Unknown-role policy (agreed): coerce to `learner` + warn-log on IFPI side.**
Rejecting unknown roles would break role sync every time ERP360 adds a role.
Suggested elevated mapping: `OWNER|MANAGER|HEAD_OF_ADMIN → ADMIN`, everything
else → `learner` unless IFPI decides otherwise.

**`scope` / `branch_id` semantics (agreed 2026-07):**
- `scope` is an enum: `ORG | BRANCH | PLATFORM` (ERP360 canonical values,
  taken from the stored role, not client input).
- `branch_id` is an ERP360-side numeric branch ID; NULL for org-wide roles.
  IFPI stores it **opaquely** — there is no shared branch registry.
- **v1 policy: IFPI accepts-and-ignores `scope`/`branch_id`** and treats every
  role as org-wide. Scope-aware authorization is a jointly designed v2.

### 6.3 HMAC signing spec (pinned — matches shipped implementation)

- Signed string: the **raw HTTP body bytes exactly as sent** — nothing
  prepended/appended (no timestamp concatenation, no nonce).
- Body serialization at ERP360: `json.dumps(payload, sort_keys=True,
  separators=(",", ":"))` — but receivers must verify raw bytes as received.
- Header: `X-ERP360-Signature: sha256=<hex hmac-sha256>`.
- Replay guard: receivers SHOULD check `X-ERP360-Timestamp` within **±5 minutes**
  and MAY reject older requests; dedupe on `X-ERP360-Event-Id` remains mandatory.
- Any change to this spec is a **v2 contract** — never mutate in place.

### 6.4 Delivery re-signing — CONFIRMED behavior

ERP360 stores only the payload, never the signature. Every delivery attempt
(including manual re-queues of dead letters) **re-signs with the current env
secret** — proven live after the 2026-07 secret rotation (delivery re-queued
post-rotation was accepted with 202).

### 6.5 Operational rules

- `SameSite=None; Secure` on IFPI auth cookies and the two-origin explicit
  `ALLOWED_ORIGINS` list are **required for cross-domain SSO — do not revert**.
- Preview/production URL rotation on either side triggers a same-day paired
  env update on the other side (all values are single-line env edits).
- Both shared secrets rotate at production cutover and every 90 days after.

## 7. Dual-mode addendum — IFPI standalone vs bolted-on (agreed 2026-07)

IFPI must run in two modes per organization: **standalone** (no ERP360) and
**bolted-on** (ERP360-connected). These four rules keep the modes from
diverging. Items 7.1–7.4 are IFPI-side build requirements; ERP360's contract
is already compatible (org-scoped payloads, stable `sub`).

### 7.1 Billing abstraction (blocks P2.1 rework)

- Per-org setting: `billing_mode: "native_stripe" | "erp360"`.
- Enrollment/access logic MUST NOT call a payment provider directly. It reads
  a single internal **entitlement** record ("learner X has paid for course Y").
- `native_stripe` mode: IFPI's Stripe checkout/webhooks write entitlements.
- `erp360` mode (P2.1): ERP360 lite-billing checkout redirects + subscription
  webhooks write the same entitlements. No enrollment-code changes at cutover.
- Merchant-of-record differs per mode (IFPI's Stripe vs ERP360 lite-billing);
  refunds/invoices/tax receipts follow the active biller. Document per org.

### 7.2 Identity link (prevents duplicate-account merges)

- IFPI stores `erp360_person_id` (nullable) on its user record.
- Native/standalone signups leave it NULL.
- On first SSO for a previously-native user: link by **verified-email match**
  (one-time), set `erp360_person_id = sub`; thereafter `sub` is authoritative
  and email changes on either side do not re-key the account.
- Never auto-create a second account when an email-matching native account
  exists.

### 7.3 Scoped role rewrite (protects IFPI-native roles)

- `role_changed` handling replaces ONLY the ERP360-managed role subset
  (the alias-mapped `ADMIN`/`learner` set from §6.2).
- IFPI-native roles (`INSTRUCTOR`, cohort assignments, etc.) are IFPI's
  source-of-truth and MUST survive any ERP360 webhook — no full rewrite.

### 7.4 Per-org connection state (no global flags)

- ERP360-connection state lives per organization (keyed on `org_slug`):
  `{erp360_connected: bool, billing_mode, sso_enabled}` — not a global env
  flag. (Global `SSO_ENABLED` is acceptable only while previews are
  single-tenant.)
- `user_deactivated` / `role_changed` handlers act only on users inside the
  connected org resolved from the payload's `org_slug`; events must never
  match users in standalone orgs (e.g. by email collision).
