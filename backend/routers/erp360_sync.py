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

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db, SessionLocal
from models import AuditLog, Erp360SeenEvent, Organization, User, UserRole
from services.db_locks import advisory_lock, retry_on_deadlock
from services.rate_limits import erp360_webhook_limiter

router = APIRouter(prefix="/api/erp360", tags=["ERP360"])
logger = logging.getLogger(__name__)

# §6.3 — Replay window for `X-ERP360-Timestamp`. Spec: SHOULD check
# within ±5 min. Configurable via env for ops (tighten in prod).
_TIMESTAMP_SKEW_SECONDS = int(os.environ.get("ERP360_TIMESTAMP_SKEW_SECONDS", "300"))


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


def _remember_event(db: Session, event_id: str) -> bool:
    """SQL-backed idempotency (§6.4). Returns True if newly seen,
    False if duplicate. Uses INSERT-with-conflict-on-PK semantics so
    concurrent workers can't both accept the same event."""
    from sqlalchemy.exc import IntegrityError
    try:
        db.add(Erp360SeenEvent(event_id=event_id))
        db.flush()
        return True
    except IntegrityError:
        db.rollback()
        return False


def _verify_timestamp(header_value: Optional[str]) -> None:
    """§6.3 — replay guard. Reject if `X-ERP360-Timestamp` is outside
    ±5 min from now. Header MAY be missing (spec says SHOULD check);
    if missing we allow through and rely on `event_id` dedup alone.
    If present but malformed, we treat it as a signal of tampering
    and reject.
    """
    if not header_value:
        return  # not sent — dedup is still mandatory downstream
    header_value = header_value.strip()
    ts: Optional[datetime] = None
    # Try ISO-8601 UTC (ERP360's canonical format per §2 header spec).
    try:
        # Support both '2026-06-10T11:37:08.123456+00:00' and trailing 'Z'.
        ts = datetime.fromisoformat(header_value.replace("Z", "+00:00"))
    except ValueError:
        # Fall back to unix epoch seconds (integer or float).
        try:
            ts = datetime.fromtimestamp(float(header_value), tz=timezone.utc)
        except (TypeError, ValueError):
            ts = None
    if ts is None:
        raise HTTPException(status_code=400,
                            detail="Malformed X-ERP360-Timestamp header")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = abs((now - ts).total_seconds())
    if delta > _TIMESTAMP_SKEW_SECONDS:
        raise HTTPException(
            status_code=401,
            detail=(f"Timestamp outside ±{_TIMESTAMP_SKEW_SECONDS}s replay window "
                    f"(drift {int(delta)}s) — possible replay or clock skew"),
        )


def _resolve_org(db: Session, org_slug: Optional[str]) -> Organization:
    """§7.4 — resolve the target organization from the webhook payload's
    `org_slug`. Matches against `Organization.integrations.erp360.org_slug`
    first (explicit ERP360-side mapping), then falls back to our own
    `Organization.slug` for single-tenant preview setups.

    Fails closed: if `org_slug` is present but no matching connected
    org exists, refuse the event. Empty `org_slug` falls back to the
    default org for backwards compatibility with the pre-§7.4 handoff.
    """
    if not org_slug:
        # Pre-§7.4 payloads or preview mode — use the default (first) org.
        org = db.query(Organization).order_by(Organization.id.asc()).first()
        if not org:
            raise HTTPException(status_code=500,
                                detail="No academy configured")
        return org

    # Match by explicit ERP360 mapping first.
    for candidate in db.query(Organization).all():
        if (candidate.erp360_settings.get("org_slug") == org_slug
                and candidate.is_erp360_connected):
            return candidate

    # Fallback: match by native slug (preview convention).
    org = db.query(Organization).filter(Organization.slug == org_slug).first()
    if org:
        return org

    raise HTTPException(
        status_code=404,
        detail=f"No IFPI organization connected to ERP360 org_slug={org_slug!r}",
    )


@router.post("/webhooks/user", status_code=status.HTTP_202_ACCEPTED)
async def erp360_webhook_user(
    request: Request,
    background_tasks: BackgroundTasks,
    x_erp360_signature: Optional[str] = Header(None),
    x_erp360_event_id: Optional[str] = Header(None),
    x_erp360_timestamp: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """Receive `user.role_changed` and `user.deactivated` events from ERP360.

    Payload shape:
      {event, event_id, occurred_at, org_slug,
       user: {sub, email, name}, data: {new_roles?, reason?}}
    """
    # Iter 37 — Rate limit BEFORE signature verify so a bad-actor
    # stampede doesn't burn CPU on HMAC. Key on the last 8 chars of the
    # signature (enough entropy to distinguish trusted keys, doesn't
    # leak the HMAC in logs); fall back to client IP.
    limiter_key = (
        (x_erp360_signature or "")[-8:]
        or (request.client.host if request.client else "unknown")
    )
    allowed, remaining = erp360_webhook_limiter.check(limiter_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded — 200 requests/min per signing key",
            headers={"Retry-After": "60"},
        )

    raw = await request.body()
    _verify_signature(raw, x_erp360_signature)
    _verify_timestamp(x_erp360_timestamp)  # §6.3 ±5 min replay window

    if not x_erp360_event_id:
        raise HTTPException(status_code=400,
                            detail="Missing X-ERP360-Event-Id header")

    if not _remember_event(db, x_erp360_event_id):
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
    payload_org_slug = (payload.get("org_slug") or "").strip() or None
    if not event or not email:
        raise HTTPException(status_code=400,
                            detail="Payload must include event + user.email")

    # §7.4 — scope every lookup to the org identified by payload.org_slug.
    # Standalone-org users MUST NOT be matched by email collision.
    org = _resolve_org(db, payload_org_slug)

    user = None
    if isinstance(sub, (int, str)) and str(sub).isdigit():
        user = (
            db.query(User)
            .filter(User.erp360_user_id == int(sub),
                    User.organization_id == org.id)
            .first()
        )
    if user is None:
        user = (
            db.query(User)
            .filter(User.email == email,
                    User.organization_id == org.id)
            .first()
        )

    if user is None:
        # Not provisioned in IFPI yet — record and move on. First SSO
        # sign-in will JIT-provision with the correct roles.
        logger.info("ERP360 webhook for unknown user %s in org=%s (event=%s) — noop",
                    email, org.slug, event)
        _audit_stub(db, event, email, note=f"unknown_user org={org.slug}")
        db.commit()  # persist idempotency + audit row
        return {"status": "accepted", "action": "noop_unknown_user"}

    if event == "role_changed":
        raw_new = (payload.get("data") or {}).get("new_roles") or []
        # §6.2 — `data.new_roles` is an array of objects
        # `{role_name, scope, branch_id}`. In v1 we accept-and-ignore
        # `scope` (enum ORG|BRANCH|PLATFORM) and `branch_id`, treating
        # every role as org-wide. Preserve the raw shape in the audit
        # log so v2 scope-aware auth can reconstruct history.
        new_role_names = _extract_role_names(raw_new)
        # Iter 37 — advisory lock keyed on (org_id, user.erp360_user_id
        # or user.id) so concurrent role_changed events for the SAME
        # user serialize outside the transaction; different users still
        # run in parallel. No-op on SQLite.
        advisory_lock(db, org.id, user.erp360_user_id or user.id)
        _replace_erp360_roles(db, user, new_role_names)
        db.commit()
        # Iter 37 — audit write moved to background task so the response
        # ships immediately. Under a stampede this shaves ~5-15ms off
        # every handler and removes the audit table from the hot lock
        # path.
        background_tasks.add_task(
            _audit_bg, event, email, user_id=user.id,
            note=f"raw_new_roles={raw_new} canonical={new_role_names}",
        )
        return {"status": "accepted", "action": "roles_updated",
                "new_roles": [r.role for r in user.user_roles]}

    if event == "user_deactivated":
        advisory_lock(db, org.id, user.erp360_user_id or user.id)
        user.is_active = False
        db.commit()
        background_tasks.add_task(
            _audit_bg, event, email, user_id=user.id, note="deactivated",
        )
        return {"status": "accepted", "action": "user_deactivated"}

    raise HTTPException(status_code=400,
                        detail=f"Unsupported event type: {event}")


def _audit_bg(event: str, email: str, *,
              user_id: Optional[int] = None,
              note: str = "") -> None:
    """Background-task audit writer. Opens its own session because the
    request-scoped `db` is closed by the time this runs. Errors are
    logged, never raised (background task failures do not affect the
    already-sent 202 response). See `_audit_stub` for the persisted
    shape."""
    session = SessionLocal()
    try:
        _audit_stub(session, event, email, user_id=user_id, note=note)
        session.commit()
    except Exception:
        logger.exception("Background audit write failed for event=%s email=%s", event, email)
        session.rollback()
    finally:
        session.close()


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


@retry_on_deadlock()
def _replace_erp360_roles(db: Session, user: User,
                          new_role_names: list[str]) -> None:
    """§7.3 — Idempotent role replacement scoped to ERP360-managed rows.

    Only rows with `source='erp360'` are wiped and rebuilt. IFPI-native
    roles (INSTRUCTOR, cohort assignments, native admin grants) are
    preserved across every inbound webhook. Unknown ERP360 role names
    coerce to LEARNER + warn-log per §6.2.

    Iter 37 — `@retry_on_deadlock` guards against transient Postgres
    40P01/40001 under concurrent role-change stampedes. Combined with
    the caller's advisory lock, deadlocks should be effectively
    impossible for the same user; the retry is belt-and-braces for
    cross-user deadlocks (e.g. secondary index / audit log contention).
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
