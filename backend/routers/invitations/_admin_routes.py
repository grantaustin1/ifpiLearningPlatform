from __future__ import annotations

from . import admin_router
from ._schemas import BulkInviteBody, InvitationCreate, InvitationOut

from datetime import datetime, timezone

from typing import List, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from models import Invitation
from services.invitation_service import InvitationService


def _status_of(inv: Invitation) -> str:
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    # SQLite stores naive datetimes — compare apples-to-apples
    exp = inv.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return "expired"
    return "pending"


@admin_router.post("", response_model=InvitationOut)
def create_invitation(body: InvitationCreate, request: Request,
                      db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    base_url = str(request.base_url).rstrip("/")
    # Strip API path remnants — invite link points at the frontend
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    inv = InvitationService(db).create(
        organization_id=current.organization_id, invited_by_id=current.id,
        email=body.email, name=body.name, role=body.role,
        app_base_url=base_url,
    )
    # §5.2 — outbound event so ERP360 (and any other subscriber) can
    # sync their identity graph on first-invite.
    from services.webhook_service import emit_safely
    emit_safely(db, current.organization_id, "learner.invited", {
        "invitation_id": inv.id,
        "email": inv.email,
        "name": inv.name,
        "role": inv.role,
        "invited_by_user_id": inv.invited_by_id,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    })
    return InvitationOut(
        id=inv.id, email=inv.email, name=inv.name, role=inv.role,
        invited_by_id=inv.invited_by_id, accepted_at=inv.accepted_at,
        revoked_at=inv.revoked_at, expires_at=inv.expires_at,
        created_at=inv.created_at, status=_status_of(inv),
    )


@admin_router.get("", response_model=List[InvitationOut])
def list_invitations(db: Session = Depends(get_db),
                     current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(Invitation).filter(
        Invitation.organization_id == current.organization_id,
    ).order_by(Invitation.created_at.desc()).all()
    return [InvitationOut(
        id=r.id, email=r.email, name=r.name, role=r.role,
        invited_by_id=r.invited_by_id, accepted_at=r.accepted_at,
        revoked_at=r.revoked_at, expires_at=r.expires_at,
        created_at=r.created_at, status=_status_of(r),
    ) for r in rows]


@admin_router.delete("/{invitation_id}")
def revoke_invitation(invitation_id: int, db: Session = Depends(get_db),
                      current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    InvitationService(db).revoke(invitation_id, current.organization_id)
    return {"ok": True}


@admin_router.post("/bulk")
def bulk_invite(body: BulkInviteBody, request: Request,
                db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Issue up to 500 invitations in one call. Each row returns its own
    {email, status, reason} so the admin sees exactly what got through.
    Optional cohort string applies to every row in the batch."""
    rows = body.invitations or []
    if len(rows) > 500:
        raise HTTPException(status_code=400, detail="Bulk invite cap is 500 rows per request")
    base_url = str(request.base_url).rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    svc = InvitationService(db)
    results = []
    queued = 0
    for row in rows:
        try:
            svc.create(
                organization_id=current.organization_id, invited_by_id=current.id,
                email=row.email, name=row.name, role=row.role, app_base_url=base_url,
                cohort=body.cohort,
            )
            results.append({"email": row.email, "status": "queued", "reason": None})
            queued += 1
        except HTTPException as he:
            results.append({"email": row.email, "status": "skipped", "reason": he.detail})
        except Exception as e:
            results.append({"email": row.email, "status": "error", "reason": str(e)[:200]})
    from services import audit_service
    audit_service.record(
        db, current, "INVITATIONS_BULK_QUEUED",
        target_type="organization", target_id=str(current.organization_id),
        metadata={"queued": queued, "total": len(rows), "cohort": body.cohort},
        request=request,
    )
    db.commit()
    return {"queued": queued, "total": len(rows), "results": results}
