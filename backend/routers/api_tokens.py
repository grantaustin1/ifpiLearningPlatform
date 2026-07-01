"""API tokens router (Iter 21).

Admin-only endpoints for issuing/managing programmatic bearer tokens.
The plaintext token is returned EXACTLY ONCE — at creation time. All
subsequent reads only see the prefix + last_used_at + scopes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.api_tokens import mint_token, TOKEN_PREFIX
from auth.dependencies import CurrentUser, requires_roles
from core.database import get_db
from core.role_registry import normalize_role_names
from models import ApiToken

router = APIRouter(prefix="/api/admin/api-tokens", tags=["API Tokens"])


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: List[str] = Field(default_factory=lambda: ["LEARNER"])
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365 * 5)


def _to_dict(t: ApiToken) -> dict:
    return {
        "id": t.id, "name": t.name,
        "prefix": f"{TOKEN_PREFIX}{t.prefix}",
        "scopes": t.scopes or [],
        "is_active": t.is_active,
        "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "created_by_id": t.created_by_id,
    }


@router.get("")
def list_tokens(db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(ApiToken).filter(
        ApiToken.organization_id == current.organization_id,
    ).order_by(ApiToken.id.desc()).all()
    return {"items": [_to_dict(t) for t in rows]}


@router.post("", status_code=201)
def create_token(body: ApiTokenCreate, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    scopes = normalize_role_names(body.scopes)
    if not scopes:
        raise HTTPException(status_code=400, detail="At least one scope is required")

    plaintext, prefix, token_hash = mint_token()
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    row = ApiToken(
        organization_id=current.organization_id,
        name=body.name.strip(),
        prefix=prefix,
        token_hash=token_hash,
        scopes=scopes,
        created_by_id=current.id,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    from services import audit_service
    audit_service.record(
        db, current, "API_TOKEN_CREATED",
        target_type="api_token", target_id=str(row.id),
        metadata={"name": row.name, "scopes": scopes,
                  "expires_in_days": body.expires_in_days},
    )
    db.commit()

    # Plaintext returned EXACTLY ONCE
    return {**_to_dict(row), "token": plaintext}


@router.post("/{token_id}/revoke")
def revoke_token(token_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    row = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.organization_id == current.organization_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    if not row.is_active:
        return {"ok": True, "already_revoked": True}
    row.is_active = False
    db.commit()

    from services import audit_service
    audit_service.record(
        db, current, "API_TOKEN_REVOKED",
        target_type="api_token", target_id=str(row.id),
        metadata={"name": row.name, "prefix": row.prefix},
    )
    db.commit()
    return {"ok": True, "id": row.id}


@router.delete("/{token_id}")
def delete_token(token_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    row = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.organization_id == current.organization_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
