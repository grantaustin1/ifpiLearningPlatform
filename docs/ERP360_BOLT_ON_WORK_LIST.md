# ERP360-Side Work List — Making IFPI a Bolt-On

> **Purpose:** hand this to the ERP360 engineering lead. Every item below is work that lives in the ERP360 codebase (or ERP360's config), not in IFPI. IFPI is already built for this — the contracts are stable and documented in `IFPI_INTEGRATION_MATRIX.md`.

## The five interfaces ERP360 must implement

Every interaction between the two apps is one of these five patterns. Everything below hangs off one of them.

1. **SSO mint (ERP360 → IFPI)** — sign a JWT, redirect the user with it.
2. **Webhook receive (IFPI → ERP360)** — HTTP POST endpoints that accept signed events.
3. **Webhook send (ERP360 → IFPI)** — HTTP POST calls with an HMAC signature.
4. **API token consume (ERP360 → IFPI)** — a stored bearer token, used server-to-server.
5. **UI embed (ERP360 → IFPI)** — a tile / link / iframe in the ERP360 frontend that opens IFPI.

---

## Priority 0 — Absolute must-haves (est. 1–2 weeks)

### P0.1 Mint SSO tokens

**Where in ERP360:** wherever `Person` identity lives, plus wherever the "Open Learning" button will be.

**Contract:** produce an HS256 JWT with the exact payload shape below and redirect the user's browser to `POST /api/auth/sso-exchange` on IFPI with the token as JSON body.

```json
{
  "iss": "erp360",
  "aud": "ifpi-lms",
  "sub": "<erp360_person_id>",
  "email": "user@company.com",
  "name": "Full Name",
  "roles": ["TRAINER", "MANAGER"],
  "org_slug": "acme",
  "iat": 1707000000,
  "exp": 1707000060,       // ≤ 60 s TTL — mint fresh every click
  "jti": "<uuidv4>"         // required, single-use
}
```

**Signing:** HMAC-SHA256 using a shared secret. ERP360 must keep this secret in a vault, never in git.

**Estimate:** 1 day (a few hours if ERP360 already has a JWT library).

**Success test:** `POST https://<ifpi>/api/erp360/sync/handshake-dry-run` with a sample token returns `{valid: true, jit_provisioned: false}` without persisting anything.

### P0.2 Store the IFPI shared secret in ERP360's environment

- Environment variable: `IFPI_SSO_SHARED_SECRET`
- Loaded by ERP360's JWT signer above
- **Rotate every 90 days** — coordinate with IFPI Ops so both sides swap on the same clock

**Estimate:** 30 minutes plus a runbook entry for rotations.

### P0.3 Add the "Open Learning Academy" UI entry point

A tile / button somewhere sensible in the ERP360 frontend (dashboard, top-nav, or Person profile). On click:

1. Front-end calls ERP360's own `POST /internal/mint-ifpi-sso` (P0.1 endpoint).
2. Gets back the JWT.
3. Redirects: `window.location = "https://<ifpi>/sso/land?token=<jwt>"` OR posts the token in a hidden form to `/api/auth/sso-exchange`.

**Estimate:** half a day, mostly design/copy decisions.

### P0.4 Send `role_changed` and `user_deactivated` webhooks to IFPI

When ERP360 fires either event internally, POST it to IFPI so IFPI's local user cache stays in sync:

```
POST https://<ifpi>/api/erp360/webhooks/user
X-ERP360-Signature: sha256=<hmac_of_body>
Content-Type: application/json

{
  "event": "user.role_changed"  |  "user.deactivated",
  "erp360_person_id": "12345",
  "email": "user@company.com",
  "new_roles": ["TRAINER"],           // only for role_changed
  "occurred_at": "2026-02-06T14:00:00Z"
}
```

**Signing:** HMAC-SHA256 of the raw request body, using the outbound secret ERP360 already has for other webhooks.

**Retry policy:** exponential backoff, at least 3 attempts over 15 minutes. Dead-letter to whatever queue ERP360 already uses.

**Estimate:** 2 days. Most of it is testing the retry path.

---

## Priority 1 — Really should be there for smooth Day 1 (est. 1 week)

### P1.1 Receive IFPI's outbound webhooks

IFPI will emit events on your endpoint (`WEBHOOK_OUTBOUND_TO_ERP360_URL`). ERP360 needs an inbound handler that:

- Verifies `X-IFPI-Signature: sha256=<hmac>` against the raw request body
- Records the event
- Idempotency: check `event_id` header — if you've seen it, return 200 and ignore

**Events ERP360 will receive:**
- `learner.invited` — someone was invited into an academy
- `enrollment.completed` — a learner finished a course
- `certificate.issued` — someone earned a certificate (⚠️ **surface this in the person's ERP360 profile — this is the whole point of the integration**)
- `ai.spend.threshold` — IFPI hit the AI budget alert threshold
- `course.published` — a course was published

**Estimate:** 3 days. Half a day is the HMAC verify; the rest is deciding what UI to show each event in ERP360.

### P1.2 Add "IFPI Training" section to the Person profile

The whole point of P1.1 above. On any Person page in ERP360, show:

- Live count of enrolments in progress
- List of certificates earned (with clickable IFPI verify links)
- Last activity date
- "Assign training" button that pre-fills an invitation on IFPI

Data comes from either (a) the webhook stream ERP360 stored locally, or (b) real-time calls to IFPI's API using an ERP360-owned API token (see P1.4).

**Estimate:** 2 days including designs.

### P1.3 SSO-cookie same-domain configuration

Both apps must serve from the same **eTLD+1** (e.g. `academy.acme.com` and `erp.acme.com` both under `acme.com`) so cookies work correctly.

If they must be on different domains, IFPI's cookie needs `SameSite=None; Secure` (already supported by `AUTH_COOKIE_SAMESITE=none`).

**Estimate:** DNS work — half a day if you own the domain, longer if IT change control involved.

### P1.4 Mint an ERP360-owned API token in IFPI

For server-to-server calls (e.g. rendering the "IFPI Training" widget from P1.2), ERP360 needs a long-lived API token from IFPI. This is a one-time setup:

1. Admin in IFPI creates a token from `Tokens → New Token` with scopes `read:catalog`, `read:analytics`, `write:learners`.
2. Copy the token once at creation. Paste into ERP360's `IFPI_API_TOKEN` env var.
3. Every ERP360 → IFPI call sends `Authorization: Bearer <token>`.

**Estimate:** 30 minutes for the human, plus wiring in ERP360's HTTP client (2 hours).

---

## Priority 2 — Nice to have, defer if pressed (est. 1–2 weeks)

### P2.1 Route IFPI billing through ERP360's lite-billing

When a customer subscribes to a paid IFPI course, ERP360 handles the money. IFPI just marks the enrolment as paid once ERP360 confirms via webhook.

**Contract:**
- IFPI redirects checkout to `${ERP360_BILLING_BASE_URL}/checkout?product=ifpi_course&course_id=X&customer_id=Y`.
- ERP360 handles the Stripe/PayFast flow.
- On success, ERP360 POSTs back to IFPI: `/api/billing/webhooks/erp360` with event `billing.subscription.activated`.

**Estimate:** 1 week. Most of it is Stripe flow work in ERP360, not IFPI integration.

### P2.2 Bidirectional branding sync

When someone changes their logo / primary colour in ERP360, push it to IFPI via `org.branding_changed` webhook. IFPI has already built the receiving side.

**Estimate:** 2 days.

### P2.3 Cross-app search

One search bar in ERP360's top-nav queries both apps. Requires:
- IFPI exposes `/api/search?q=…` (already exists)
- ERP360's search widget calls both, merges results, tags source

**Estimate:** 3 days.

### P2.4 Shared feature flags

Wire ERP360's LaunchDarkly (or whatever) into IFPI so a single flag toggle affects both. IFPI's `FeatureFlag` model already accepts per-org overrides — a webhook on flag change would do it.

**Estimate:** 2 days.

---

## Priority 3 — Long-term integration polish (defer to post-launch)

- Unified audit log — replicate IFPI's audit events into ERP360's central stream
- SSO to third apps too (Slack, Notion) via ERP360 as the identity broker
- Shared "team" abstraction — a cohort in IFPI == a department in ERP360

---

## The environment variables ERP360 needs to hold

| Variable | Purpose | Set by |
|---|---|---|
| `IFPI_SSO_SHARED_SECRET` | HMAC secret for signing SSO JWTs | Platform Ops (shared with IFPI Ops) |
| `IFPI_BASE_URL` | Root URL of IFPI (e.g. `https://academy.acme.com`) | Platform Ops |
| `IFPI_API_TOKEN` | Bearer token for server-to-server calls | Admin creates in IFPI, one-time paste |
| `IFPI_WEBHOOK_INBOUND_SECRET` | HMAC secret ERP360 uses to verify webhooks FROM IFPI | Platform Ops (shared with IFPI Ops) |
| `IFPI_WEBHOOK_OUTBOUND_URL` | Where ERP360 sends webhooks TO IFPI | Platform Ops |
| `IFPI_WEBHOOK_OUTBOUND_SECRET` | HMAC secret for signing webhooks TO IFPI | Platform Ops |

Six secrets total. Store them all in ERP360's existing secrets vault. Rotate every 90 days on a shared calendar.

---

## Verifying the integration works

Once ERP360's work is done, run these three checks against a staging tenant:

1. **`GET https://<ifpi>/api/erp360/sync/status`** — should return `{"sso": true, "webhook_outbound_healthy": true}`.
2. **`POST https://<ifpi>/api/erp360/sync/test-ping`** — fires a synthetic outbound webhook to ERP360; ERP360 must return 200.
3. **Click "Open Learning Academy" from a real ERP360 Person page** — user lands on IFPI already signed in, with the correct role, and their Person profile in ERP360 now shows an "IFPI training" section.

If all three green, the bolt-on is live.

---

## Total estimate

| Priority | Effort | Delivered value |
|---|---|---|
| **P0 (must-have)** | 1–2 weeks of one engineer | Basic SSO + user sync working |
| **P1 (Day-1 polish)** | 1 week | Full staff-facing UX — cert widgets, cross-app awareness |
| **P2 (nice-to-have)** | 1–2 weeks | Billing consolidation, branding sync |
| **P3 (long-term)** | Backlog | Search, unified audit, feature flags |

**Realistic go-live with P0 + P1 only:** ~3 weeks of ERP360 engineering time.

---

## What IFPI already does not need from ERP360

For clarity, so ERP360's team don't waste effort:

- ❌ Don't build a "user management" screen in ERP360 for IFPI users — IFPI has one and it's the source of truth for anything IFPI-specific (cohorts, roles like INSTRUCTOR).
- ❌ Don't build a course editor in ERP360. IFPI's Course Builder is the workflow.
- ❌ Don't build certificate rendering in ERP360. IFPI generates PDFs; ERP360 just links to them.
- ❌ Don't sync IFPI's audit log wholesale — it grows fast. Only mirror the critical events.
- ❌ Don't cache IFPI course data in ERP360. Always fetch live via the API token — IFPI's response times are <100ms.

*Owner: Platform Ops joint session with ERP360 engineering. Update whenever a new bolt-on point is agreed.*
