"""ERP360 inbound integration surface (Iter 34b).

Endpoints ERP360 calls INTO IFPI:
  POST /api/erp360/webhooks/user   — role_changed / user_deactivated events
  GET  /api/erp360/sync/status     — readiness probe (no auth)
  POST /api/erp360/sync/test-ping  — round-trip test (admin only)

Contract mirrors the ERP360-side handoff doc verbatim:
  - HMAC-SHA256 of raw body bytes in `X-ERP360-Signature: sha256=<hex>`
  - Idempotency via `X-ERP360-Event-Id` header
  - Signing key from `IFPI_WEBHOOK_OUTBOUND_SECRET` env var (same value on both sides)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from models import AuditLog, User, UserRole

router = APIRouter(prefix="/api/erp360", tags=["ERP360"])
logger = logging.getLogger(__name__)

# In-memory idempotency guard. Prod deployments with >1 replica should
# swap this for the same `sso_jti_seen` table pattern used for SSO.
_SEEN_EVENT_IDS: set[str] = set()
_SEEN_LIMIT = 10_000  # bound memory


def _shared_secret() -> Optional[str]:
    return (
        os.environ.get("IFPI_WEBHOOK_OUTBOUND_SECRET")
        or os.environ.get("ERP360_WEBHOOK_OUTBOUND_SECRET")
    )


def _verify_signature(raw: bytes, header_value: Optional[str]) -> None:
    """Constant-time HMAC verify. Raises 401 if invalid."""
    secret = _shared_secret()
    if not secret:
        raise HTTPException(status_code=503,
                            detail="ERP360 integration disabled — no shared secret configured")
    if not header_value or not header_value.startswith("sha256="):
        raise HTTPException(status_code=401,
                            detail="Missing or malformed X-ERP360-Signature header")
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    provided = header_value.split("=", 1)[1].strip()
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Signature mismatch")


def _remember_event(event_id: str) -> bool:
    """Returns True if newly seen, False if duplicate. Bounded memory."""
    if event_id in _SEEN_EVENT_IDS:
        return False
    if len(_SEEN_EVENT_IDS) >= _SEEN_LIMIT:
        _SEEN_EVENT_IDS.clear()  # coarse but safe — worst case we re-process
    _SEEN_EVENT_IDS.add(event_id)
    return True


@router.post("/webhooks/user", status_code=status.HTTP_202_ACCEPTED)
async def erp360_webhook_user(
    request: Request,
    x_erp360_signature: Optional[str] = Header(None),
    x_erp360_event_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """Receive `user.role_changed` and `user.deactivated` events from ERP360.

    Payload shape:
      {event, event_id, occurred_at, org_slug,
       user: {sub, email, name}, data: {new_roles?, reason?}}
    """
    raw = await request.body()
    _verify_signature(raw, x_erp360_signature)

    if not x_erp360_event_id:
        raise HTTPException(status_code=400,
                            detail="Missing X-ERP360-Event-Id header")

    if not _remember_event(x_erp360_event_id):
        # Duplicate — ERP360 may be retrying. Return 200 idempotently.
        return {"status": "duplicate", "event_id": x_erp360_event_id}

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body is not valid JSON")

    event = payload.get("event")
    # Iter 34b-fix — accept both undotted (canonical, ERP360's shape)
    # and dotted forms so a single deployment supports both dispatcher
    # conventions. ERP360's handoff doc uses the undotted form.
    _EVENT_ALIASES = {
        "role_changed": "role_changed",
        "user.role_changed": "role_changed",
        "user_deactivated": "user_deactivated",
        "user.deactivated": "user_deactivated",
    }
    event = _EVENT_ALIASES.get(event, event)
    user_block = payload.get("user") or {}
    email = (user_block.get("email") or "").lower().strip()
    sub = user_block.get("sub")
    if not event or not email:
        raise HTTPException(status_code=400,
                            detail="Payload must include event + user.email")

    user = (
        db.query(User).filter_by(erp360_user_id=int(sub)).first()
        if isinstance(sub, (int, str)) and str(sub).isdigit() else None
    ) or db.query(User).filter(User.email == email).first()

    if user is None:
        # Not provisioned in IFPI yet — record and move on. First SSO
        # sign-in will JIT-provision with the correct roles.
        logger.info("ERP360 webhook for unknown user %s (event=%s) — noop",
                    email, event)
        _audit_stub(db, event, email, note="unknown_user")
        return {"status": "accepted", "action": "noop_unknown_user"}

    if event == "role_changed":
        raw_new = (payload.get("data") or {}).get("new_roles") or []
        # §6.2 — `data.new_roles` is an array of objects
        # `{role_name, scope, branch_id}`. In v1 we accept-and-ignore
        # `scope` (enum ORG|BRANCH|PLATFORM) and `branch_id`, treating
        # every role as org-wide. Preserve the raw shape in the audit
        # log so v2 scope-aware auth can reconstruct history.
        new_role_names = _extract_role_names(raw_new)
        _replace_erp360_roles(db, user, new_role_names)
        _audit_stub(db, event, email, user_id=user.id,
                    note=f"raw_new_roles={raw_new} canonical={new_role_names}")
        db.commit()
        return {"status": "accepted", "action": "roles_updated",
                "new_roles": [r.role for r in user.user_roles]}

    if event == "user_deactivated":
        user.is_active = False
        _audit_stub(db, event, email, user_id=user.id, note="deactivated")
        db.commit()
        return {"status": "accepted", "action": "user_deactivated"}

    raise HTTPException(status_code=400,
                        detail=f"Unsupported event type: {event}")


def _extract_role_names(raw_new_roles) -> list[str]:
    """Unpack §6.2 role objects to their canonical `role_name` strings.

    ERP360 sends `data.new_roles` as an array of objects
    `{role_name, scope, branch_id}`. For back-compat we also accept
    bare strings (pre-§6 payloads and tests). `scope` and `branch_id`
    are accepted-and-ignored in v1 (see §6.2 pin).
    """
    out: list[str] = []
    for item in raw_new_roles or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            name = item.get("role_name") or item.get("role")
            if isinstance(name, str) and name:
                out.append(name)
        # Anything else is silently ignored — v1 policy is
        # accept-and-forward, don't reject on unknown vocabulary.
    return out


def _replace_erp360_roles(db: Session, user: User,
                          new_role_names: list[str]) -> None:
    """§7.3 — Idempotent role replacement scoped to ERP360-managed rows.

    Only rows with `source='erp360'` are wiped and rebuilt. IFPI-native
    roles (INSTRUCTOR, cohort assignments, native admin grants) are
    preserved across every inbound webhook. Unknown ERP360 role names
    coerce to LEARNER + warn-log per §6.2.
    """
    from core.role_registry import normalize_role_name  # local — avoid cycle
    canonical: set[str] = set()
    for r in new_role_names:
        if not r:
            continue
        norm = normalize_role_name(r)
        if norm is None or norm == "":
            logger.warning("ERP360 role_changed: unknown role %r → coerced to LEARNER", r)
            canonical.add("LEARNER")
        else:
            canonical.add(norm)
    if not canonical:
        canonical.add("LEARNER")

    # Wipe ONLY the ERP360-managed subset. Native roles survive.
    db.query(UserRole).filter_by(user_id=user.id, source="erp360").delete()

    # Re-insert the new ERP360 set. Skip roles the user already holds
    # from the native side to respect the unique constraint on (user, role).
    native_roles = {ur.role for ur in user.user_roles if ur.source != "erp360"}
    for role in canonical:
        if role in native_roles:
            # Already granted natively — no need to duplicate as erp360-sourced.
            # The user keeps the role regardless of ERP360's later state.
            continue
        db.add(UserRole(user_id=user.id, role=role, source="erp360"))


def _audit_stub(db: Session, event: str, email: str, *,
                user_id: Optional[int] = None,
                note: str = "") -> None:
    """Minimal audit — full audit_service.record requires an actor which
    we don't have on inbound webhooks. Use a synthetic system entry."""
    db.add(AuditLog(
        organization_id=1,  # falls under IFPI Main org for inbound events
        actor_user_id=None,
        action=f"ERP360_{event.upper().replace('.', '_')}",
        target_type="user",
        target_id=str(user_id) if user_id else email,
        audit_metadata={"note": note, "email": email},
        created_at=datetime.now(timezone.utc),
    ))


@router.get("/sync/status")
def erp360_sync_status() -> dict:
    """Public probe. Returns whether IFPI is ready to receive ERP360
    inbound traffic. No auth so ERP360 can call this during boot."""
    secret_configured = bool(_shared_secret())
    sso_configured = bool(os.environ.get("ERP360_SSO_SHARED_SECRET"))
    return {
        "sso": sso_configured,
        "webhook_outbound_healthy": secret_configured,
        "ready": secret_configured and sso_configured,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/sync/test-ping")
def erp360_sync_test_ping(
    current: CurrentUser = Depends(requires_admin()),
    db: Session = Depends(get_db),
) -> dict:
    """Round-trip verification. Currently a stub — synthetic outbound
    webhook dispatch will land in a follow-up.

    For now, returns confirmation that the caller is authenticated as
    an admin AND the inbound integration surface is live. That's enough
    for ERP360's engineer to know they're pointed at the right host.
    """
    return {
        "ok": True,
        "actor_email": current.email,
        "org_id": current.organization_id,
        "inbound_secret_configured": bool(_shared_secret()),
        "message": (
            "Inbound surface reachable. Full outbound-webhook dispatch "
            "will be wired in P1 (ERP360-side handoff item 4)."
        ),
    }
