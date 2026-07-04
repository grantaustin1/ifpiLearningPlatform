# IFPI Outgoing Webhook Events

This document describes every event that the IFPI Learning platform emits to
externally-registered webhook subscribers. Register a subscription via
`POST /api/admin/webhooks` — see `docs/IFPI_INTEGRATION_MATRIX.md` for the
full integration playbook (URL, secret, event list, HMAC signing).

Every delivery ships with these headers:

| Header | Meaning |
| ------ | ------- |
| `Content-Type` | `application/json` |
| `X-IFPI-Event` | The `event_type` string (also inside the payload) |
| `X-IFPI-Delivery-Id` | Unique delivery id — use for idempotent processing |
| `X-IFPI-Signature` | `sha256=<hex>` HMAC of the raw body, keyed on your subscription's `secret` |

Your handler **must** verify the signature and treat duplicate delivery ids
as no-ops. Retries follow an exponential backoff: 30s → 5min → 30min before
the event lands in the dead-letter queue.

---

## Certificate lifecycle

### `certificate.issued`

Fired when a certificate is created — course completion, live-session
attendance, or bulk import.

```json
{
  "certificate_id": 4218,
  "code": "9c1a1c9df2c14d…",
  "user_id": 91,
  "type": "COURSE_COMPLETION",
  "issued_at": "2026-02-11T09:07:24.000Z",
  "course_id": 12,
  "score": 88
}
```

Notes:
- `type` is one of `COURSE_COMPLETION`, `LIVE_SESSION_ATTENDANCE`.
- `course_id` is `null` for attendance certs; `live_session_id` is present
  instead.

---

### `certificate.revoked`

Fired when an admin revokes a certificate — either a single-cert revoke
(`POST /api/certificates/{id}/revoke`) or a bulk revoke
(`POST /api/certificates/bulk-revoke`). **Idempotent**: re-revoking to
update the reason does NOT fire a second event.

```json
{
  "certificate_id": 4218,
  "code": "9c1a1c9df2c14d…",
  "user_id": 91,
  "type": "COURSE_COMPLETION",
  "reason": "Issued in error — learner not eligible",
  "revoked_at": "2026-02-11T14:32:07.000Z",
  "actor_user_id": 4,
  "bulk": false
}
```

Fields:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `certificate_id` | int | Primary key of the revoked cert |
| `code` | string | Public share code — matches `/verify/{code}` |
| `user_id` | int | The learner who held the cert |
| `type` | string | See `certificate.issued` for enum |
| `reason` | string \| null | Admin-provided reason, ≤255 chars |
| `revoked_at` | ISO-8601 string | UTC timestamp |
| `actor_user_id` | int | Admin who initiated the revocation |
| `bulk` | bool | `true` when part of a `POST /bulk-revoke` batch |

Recommended handler behaviour:
- Mark the credential invalid in your HR/LMS integration.
- Trigger a badge-badge-invalidation flow on LinkedIn (via their partner API).
- Alert your compliance officer if the actor is not on an approved list.

---

### `certificate.unrevoked`

Fired when an admin lifts a revocation, either via
`POST /api/certificates/{id}/unrevoke` or the bulk endpoint. Also
idempotent — unrevoking an already-active cert emits nothing.

```json
{
  "certificate_id": 4218,
  "code": "9c1a1c9df2c14d…",
  "user_id": 91,
  "type": "COURSE_COMPLETION",
  "actor_user_id": 4,
  "bulk": true
}
```

Recommended handler behaviour: reinstate the credential in downstream
systems. There is no `unrevoked_at` field — the current server time at
delivery is authoritative.

---

## Enrollment lifecycle

### `enrollment.completed`

Emitted when a learner's course progress crosses 100%.

```json
{
  "enrollment_id": 812,
  "user_id": 91,
  "course_id": 12,
  "completed_at": "2026-02-11T09:07:20.000Z",
  "progress": 1.0
}
```

---

### `enrollment.created`

Emitted when a learner enrolls in a course (self-enroll or admin-assigned).

```json
{
  "enrollment_id": 812,
  "user_id": 91,
  "course_id": 12,
  "enrolled_at": "2026-02-10T08:30:00.000Z"
}
```

---

## Exam lifecycle

### `exam.attempt.completed`

```json
{
  "attempt_id": 44,
  "exam_id": 8,
  "user_id": 91,
  "score": 82,
  "passed": true,
  "completed_at": "2026-02-11T09:05:00.000Z"
}
```

---

## Live sessions

### `live_session.rsvped`

```json
{
  "session_id": 30,
  "user_id": 91,
  "rsvp_status": "RSVP",
  "start_at": "2026-02-14T13:00:00.000Z"
}
```

### `live_session.attended`

Emitted when an admin marks a learner as `ATTENDED` (which may then trigger
`certificate.issued` for an attendance certificate).

```json
{
  "session_id": 30,
  "user_id": 91,
  "attended_at": "2026-02-14T13:56:00.000Z"
}
```

---

## Verification

Every event body is signed. Node.js verifier:

```js
import crypto from 'crypto'

function verify(req, secret) {
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(req.rawBody)  // Buffer — do NOT parse first
    .digest('hex')
  const provided = req.headers['x-ifpi-signature']
  return crypto.timingSafeEqual(
    Buffer.from(expected), Buffer.from(provided))
}
```

Python:

```python
import hmac, hashlib

def verify(raw_body: bytes, provided: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(
        secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)
```

---

## Retry & dead-letter

Deliveries retry on any non-2xx response with the following schedule:

| Attempt | Delay |
| ------- | ----- |
| 1 | immediate |
| 2 | +30s |
| 3 | +5min |
| 4 | +30min |

After the 4th failure the row's `status` becomes `DEAD_LETTER`. Admins can
inspect and manually re-queue via `POST /api/admin/webhooks/{sub}/deliveries/{id}/retry`.

---

## See also

- `docs/IFPI_INTEGRATION_MATRIX.md` — full integration playbook + example
  Slack / Discord / LinkedIn receivers
- `docs/ERP360_INTEGRATION.md` — SSO + billing counterpart to this doc
