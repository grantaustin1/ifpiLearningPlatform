"""Admin invitations: create/list/revoke + public token endpoints (lookup, accept)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from auth.cookies import set_auth_cookie, set_refresh_cookie, should_include_token_in_body
from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.config import settings
from core.database import get_db
from models import Invitation
from schemas import LoginResponse, UserOut
from services.auth_service import AuthService
from services.invitation_service import ALLOWED_INVITE_ROLES, InvitationService


class InvitationCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    role: str = "INSTRUCTOR"


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: Optional[str]
    role: str
    invited_by_id: Optional[int]
    accepted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime
    status: str


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


admin_router = APIRouter(prefix="/api/admin/invitations", tags=["Invitations"])


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


class BulkInviteRow(BaseModel):
    email: str
    name: Optional[str] = None
    role: str = "LEARNER"


class BulkInviteBody(BaseModel):
    invitations: List[BulkInviteRow]
    cohort: Optional[str] = None


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
            inv = svc.create(
                organization_id=current.organization_id, invited_by_id=current.id,
                email=row.email, name=row.name, role=row.role, app_base_url=base_url,
            )
            if body.cohort:
                inv.cohort = body.cohort
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


# ── Public endpoints (no auth — keyed by opaque token) ───────────────
public_router = APIRouter(prefix="/api/invitations", tags=["Invitations"])


class InvitationAccept(BaseModel):
    password: str
    name: Optional[str] = None


class InvitationLookup(BaseModel):
    email: str
    name: Optional[str]
    role: str
    organization_name: str


@public_router.get("/{token}", response_model=InvitationLookup)
def lookup_invitation(token: str, db: Session = Depends(get_db)):
    inv = InvitationService(db).lookup(token)
    from models import Organization
    org = db.query(Organization).filter(Organization.id == inv.organization_id).first()
    return InvitationLookup(
        email=inv.email, name=inv.name, role=inv.role,
        organization_name=org.name if org else "IFPI Learning",
    )


@public_router.post("/{token}/accept", response_model=LoginResponse)
def accept_invitation(token: str, body: InvitationAccept, response: Response,
                      db: Session = Depends(get_db)):
    svc = InvitationService(db)
    user = svc.accept(token, password=body.password, name=body.name)
    access, refresh = AuthService(db).issue_tokens(user)
    set_auth_cookie(response, access)
    set_refresh_cookie(response, refresh)
    from core.role_registry import normalize_role_names
    roles = normalize_role_names([ur.role for ur in user.user_roles]) or ["LEARNER"]
    return LoginResponse(
        access_token=access if should_include_token_in_body() else None,
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserOut(
            id=user.id, email=user.email, name=user.name,
            organization_id=user.organization_id, roles=roles, points=user.points or 0,
        ),
    )
