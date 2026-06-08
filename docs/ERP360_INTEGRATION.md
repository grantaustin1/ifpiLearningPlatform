# IFPI ↔ ERP360 Integration Reference

This document is a **paste-ready reference** for the ERP360 team to wire the
outgoing HMAC-signed webhooks IFPI already emits. IFPI itself runs standalone
today — none of the code below needs to be added to IFPI. It's for ERP360's
codebase when (and if) you decide to bolt the two together.

---

## 1) What IFPI sends

When `BILLING_LIVE_MODE=true` and `ERP360_BASE_URL` is set, the IFPI outbox
worker (`services/outbox_worker.py`) dispatches notifications to ERP360 by
POSTing to:

```
POST {ERP360_BASE_URL}/api/notifications/send
Content-Type: application/json
X-Signature: <hex HMAC-SHA256 of (raw_body + timestamp_string)>
X-Timestamp: <unix epoch seconds, string>
X-Service-Token: <ERP360_SSO_SHARED_SECRET>
```

Body shape (already JSON-serialised before signing):

```json
{
  "to": [{"email": "alice@example.com", "name": "Alice"}],
  "subject": "Your certificate is ready",
  "html": "<p>Congratulations…</p>",
  "text": "Congratulations…",
  "template": "course_completed",
  "metadata": {"ifpi_outbox_id": 42, "ifpi_user_id": 7},
  "attachments_metadata": [{"filename": "cert.pdf", "url": "/api/uploads/files/…"}]
}
```

The signature helper lives at `routers/iter5.py::sign_outgoing_payload`.

---

## 2) What ERP360 needs to add

A single FastAPI route. Drop this into `erp360/backend/routers/notifications.py`
(or wherever the ERP360 team puts incoming webhooks):

```python
import hmac, hashlib, time
from fastapi import APIRouter, HTTPException, Header, Request
from core.config import settings  # ERP360's settings module

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# Reject signatures older than this many seconds to mitigate replay attacks.
MAX_SKEW_SECONDS = 300


def _verify(raw_body: bytes, signature: str, timestamp: str) -> bool:
    if not (signature and timestamp):
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > MAX_SKEW_SECONDS:
        return False
    secret = settings.ifpi_shared_secret.encode()  # same string IFPI uses
    expected = hmac.new(secret, raw_body + timestamp.encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/send")
async def receive_notification(
    request: Request,
    x_signature: str = Header(default=""),
    x_timestamp: str = Header(default=""),
):
    raw = await request.body()
    if not _verify(raw, x_signature, x_timestamp):
        raise HTTPException(status_code=401, detail="Bad signature")
    payload = await request.json()

    # … hand off to your existing notification dispatcher
    # message_id = mail_service.send(
    #     to=payload["to"],
    #     subject=payload["subject"],
    #     html=payload["html"],
    #     attachments_metadata=payload.get("attachments_metadata") or [],
    #     metadata=payload.get("metadata") or {},
    # )
    return {"ok": True, "message_id": "stub-replace-me"}
```

ERP360 should set the same shared secret IFPI uses, e.g. in `.env`:

```
IFPI_SHARED_SECRET=<same value as IFPI ERP360_SSO_SHARED_SECRET>
```

---

## 3) Lead-capture webhook (same pattern)

IFPI also forwards lead-capture events to ERP360 in live mode. Same verification
logic, route lives at `POST /api/leads/ingest` on ERP360.

---

## 4) End-to-end smoke test

```bash
# On IFPI:
export BILLING_LIVE_MODE=true
export ERP360_BASE_URL=https://erp360.example.com
export ERP360_SSO_SHARED_SECRET=$(openssl rand -hex 32)
sudo supervisorctl restart backend

# Trigger a notification (course completion will queue an outbox row):
# Worker picks it up within 5s and POSTs to ERP360.

# Check IFPI's outbox table — status should go QUEUED → SENT.
# Check ERP360's logs — should see 401 (bad signature) attempts denied,
# then 200 once secret matches.
```

---

## 5) Decision matrix

| ERP360 not wired (today) | ERP360 wired |
|---|---|
| `BILLING_LIVE_MODE=false` (default) | Set `BILLING_LIVE_MODE=true` |
| Outbox stamps QUEUED → STUB | Outbox stamps QUEUED → SENT |
| Signatures emitted but never received | Signatures verified by ERP360 |
| IFPI fully functional standalone | IFPI emails delivered via ERP360 |

No code changes on IFPI's side — only env vars.

---

*Last reviewed: 2026-02-08. Maintained by the IFPI team. Questions: tag @ifpi-eng.*
