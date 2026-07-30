# Billing Gateway Spec — IFPI Review Answers

> Fill this in, commit it in the IFPI repo, and send it back to the ERP360 team.
> Spec under review: `docs/BILLING_GATEWAY_API_SPEC.md` (DRAFT v0.1, mirrored from ERP360).
> Reviewers: IFPI Engineering  Date: 2026-07-30

## Overall verdict
- [ ] APPROVED as-is
- [x] APPROVED with the changes noted below
- [ ] NEEDS DISCUSSION (call required)

The shapes are compatible with what IFPI has already shipped. B1 (per-org
connection state under `Organization.integrations.erp360`, admin PATCH at
`/api/admin/organizations/{id}/integrations/erp360`) and B2 (the
`EntitlementService` provider abstraction — enrollment/access-gate code does
NOT branch on `billing_mode`) are both landed, so implementing this contract
behind our provider interface is a webhook-writer swap, exactly as the spec's
§6 assumes. Change requests below are minor and none block Phase 0 sign-off.

## Answers to the 5 open questions (spec section 9)

### Q1 — Recurring collection methods at launch
Does IFPI need `CARD` recurring at launch, or is `DEBIT_ORDER`-only acceptable
for phase 2 (SA market)?

**Answer:** `DEBIT_ORDER`-only is acceptable for Phase 2. IFPI already has
native Stripe (test-mode wired end-to-end) for card recurring under
`billing_mode: native_stripe`, so orgs that need card collection at launch can
stay on the native provider. `CARD` via the gateway is a nice-to-have for
Phase 3 — do not let it delay the QLink debit-order path, which is the whole
point of bolting on for SA orgs.

### Q2 — Webhook receiver topology
One global endpoint with `org_slug` routing, or per-org URLs?
(ERP360 supports either; per-org preferred for isolation.)

**Answer:** **One global endpoint with `org_slug` routing**, mirroring our
existing user-sync receiver (`/api/erp360/webhooks/user`). That receiver
already resolves `org_slug` against per-org connection state and **fails
closed** when the slug doesn't match a connected org, giving us the isolation
property without N URLs. Per-org URLs add config drift risk on both sides
(every org onboarding needs a URL exchange). Proposed receiver:
`POST /api/erp360/webhooks/billing`, secret `BILLING_GATEWAY_WEBHOOK_SECRET`
(distinct from the user-sync secret, per §2.2), same SQL-backed `event_id`
idempotency store, same ±5 min timestamp window.

### Q3 — Customer auto-linking via SSO
Should `customers` auto-link via SSO `sub` when present, making
`external_ref` optional for bolted-on orgs?

**Answer:** Yes to auto-linking, **no to making `external_ref` optional**.
Keep `external_ref` required and unique-per-org always — it is our stable
idempotency/reconciliation key and must not depend on whether the user arrived
via SSO. Auto-link via SSO `sub` should be an enrichment: when we send a
`sub`-derived `erp360_person_id`, link to it; when we don't, create the
BILLING_ONLY person. Suggested tweak: accept an optional `sso_sub` field so
IFPI doesn't need to resolve `erp360_person_id` itself — ERP360 resolves
`sub → person` server-side (it owns that mapping).

### Q4 — Read surface for IFPI billing screens
Minimum GET endpoints IFPI needs (e.g., `GET /subscriptions/{id}/invoices`?).

**Answer:** Minimum for v1:
- `GET /customers/{customer_id}`
- `GET /checkout-intents/{id}` (poll fallback when a webhook is delayed)
- `GET /subscriptions/{id}` and `GET /subscriptions?customer_id=`
- `GET /subscriptions/{id}/transactions` (or `/invoices`) — collection history
  (date, amount, status, failure reason) so our billing screen can render a
  payment history without us reconstructing it purely from webhooks. This can
  land in v1.1 if it slips, but it's the one read we'll definitely need.

Not needed: any ledger/accounting export (per §7 non-goals, agreed).

### Q5 — Tax handling
Confirm IFPI renders VAT-inclusive gross amounts only and never recomputes tax.

**Answer:** Confirmed. IFPI displays `amount` + `currency` exactly as received
(minor units, VAT-inclusive gross) and performs no tax computation anywhere.
One ask: include an optional `vat_rate_bps` or `tax_note` string in webhook
`data` / GET responses so our invoices-style screens can *label* the amount as
VAT-inclusive without hardcoding SA VAT knowledge.

## Shape sign-off checklist (spec sections 2-6)
- [x] Auth model (per-org `bgw_` scoped tokens, dual-active rotation) — OK for our provider impl
- [x] `customers` resource shape — OK (see Q3 tweak: optional `sso_sub`)
- [x] `checkout-intents` shape + hosted `checkout_url` redirect flow — OK
- [x] `subscriptions` shape + `PENDING_MANDATE -> ACTIVE -> PAST_DUE -> SUSPENDED -> CANCELLED` lifecycle — OK
- [x] Webhook event list + envelope (reuses the pinned section 6.3 HMAC spec) — OK
- [x] Error model + `Idempotency-Key` semantics — OK
- [x] Standalone <-> bolted-on kill-switch semantics (no data migration) — compatible with our B1 per-org state
- [x] Our `billing_mode: native_stripe | erp360` abstraction (B2) can implement this behind the provider interface

## Additional change requests / concerns

1. **Sandbox before Phase 1.** We need a test-mode gateway token + a webhook
   simulator (or a `X-Test-Mode: true` flag) so IFPI can build and CI-test the
   receiver + provider impl before ERP360's PSP path is live. Our test suite
   runs fully offline; a documented "signed sample payload" fixture set for all
   10 events would be enough.
2. **`checkout.*` webhook `data` must echo the intent's `external_ref`**
   (the consumer order id), not only `checkout_intent_id` — the spec's sample
   envelope shows `external_ref` for the plan on subscription events but the
   checkout events don't list their fields. Please pin the full `data` schema
   per event in v0.2.
3. **Retry tail is short.** 60s/300s then dead-letter after 3 attempts means a
   ~6-minute outage on our side drops an entitlement-bearing event into the
   dead-letter queue. We can self-heal by polling `GET /checkout-intents/{id}`,
   but please either (a) add one long-tail retry (e.g., +1h), or (b) expose a
   `GET /events?since=` replay/backfill read so recovery is consumer-driven
   rather than "ask ERP360 staff to re-queue".
4. **`503 GATEWAY_UNAVAILABLE` should include `Retry-After`** so our checkout
   UI can show an honest wait estimate (per principle 2, only the payment
   moment may block and must fail gracefully).
5. **Rate limits (429): publish the actual budget** (req/min per token) in
   v0.2 so we can size client-side throttling.

## IFPI-side prerequisites we commit to before Phase 2
- [x] B2 entitlement abstraction landed (`services/entitlement_service.py`, Iter 39)
- [x] B1 per-org connection state landed (`integrations.erp360` on Organization, Iter 36/39)
- [ ] Webhook receiver ready for the 10 billing events (idempotent on event_id) —
      will be built as `POST /api/erp360/webhooks/billing` reusing the existing
      HMAC verify + `Erp360SeenEvent` idempotency store; scheduled once the
      sandbox fixtures from change request #1 are available.
