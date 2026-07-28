from __future__ import annotations

from . import public_router
from ._schemas import InvitationAccept, InvitationLookup

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from auth.cookies import set_auth_cookie, set_refresh_cookie, should_include_token_in_body
from core.config import settings
from core.database import get_db
from core.role_registry import normalize_role_names
from schemas import LoginResponse, UserOut
from services.auth_service import AuthService
from services.invitation_service import InvitationService


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
    roles = normalize_role_names([ur.role for ur in user.user_roles]) or ["LEARNER"]
    return LoginResponse(
        access_token=access if should_include_token_in_body() else None,
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserOut(
            id=user.id, email=user.email, name=user.name,
            organization_id=user.organization_id, roles=roles, points=user.points or 0,
        ),
    )
