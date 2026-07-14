"""Admin: per-org ERP360 integration configuration (Iter 39 P1).

Backing model shipped in Iter 36 (`Organization.integrations` JSONB with
`erp360_settings` / `is_erp360_connected` / `erp360_org_slug` /
`erp360_sso_enabled` helpers). This router exposes the read + write
surface so ops can toggle per-org SSO / connection state without
direct DB access.

Endpoints:
- `GET   /api/admin/organizations`                              — list all orgs (super_admin only)
- `GET   /api/admin/organizations/{org_id}/integrations/erp360` — read integration config
- `PATCH /api/admin/organizations/{org_id}/integrations/erp360` — merge-update config

The PATCH accepts any subset of {connected, org_slug, sso_enabled,
billing_mode}. Unspecified fields are preserved. Setting a field to
`null` explicitly clears it.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin, requires_roles
from core.database import get_db
from models import Organization
from services import audit_service
from services.cache import cache_delete


router = APIRouter(prefix="/api/admin/organizations",
                   tags=["Admin: Organizations"])


class OrgSummary(BaseModel):
    id: int
    slug: str
    name: str
    erp360_connected: bool
    erp360_sso_enabled: bool
    erp360_org_slug: Optional[str] = None
    billing_mode: Optional[str] = None


@router.get("", response_model=List[OrgSummary])
def list_organizations(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(requires_roles("SUPER_ADMIN")),
):
    """List every org in the deployment (super-admin only — regular
    admins are scoped to their own org)."""
    rows = db.query(Organization).order_by(Organization.id.asc()).all()
    return [
        OrgSummary(
            id=o.id, slug=o.slug, name=o.name,
            erp360_connected=o.is_erp360_connected,
            erp360_sso_enabled=o.erp360_sso_enabled,
            erp360_org_slug=o.erp360_settings.get("org_slug"),
            billing_mode=o.erp360_settings.get("billing_mode"),
        )
        for o in rows
    ]


class Erp360IntegrationOut(BaseModel):
    organization_id: int
    organization_slug: str
    connected: bool
    sso_enabled: bool
    org_slug: Optional[str] = None
    billing_mode: Optional[str] = None
    # Full JSON blob for advanced ops that need to inspect anything else
    # we might store in there in future (e.g. per-org webhook secrets).
    raw: dict


def _load_org(db: Session, current: CurrentUser, org_id: int) -> Organization:
    """Load an org the caller is entitled to see. SUPER_ADMIN can see
    every org; regular ADMIN is scoped to their own."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    is_super = "SUPER_ADMIN" in current.roles
    if not is_super and org.id != current.organization_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Regular admins can only manage their own organization. "
                "Ask a super-admin for cross-org changes."
            ),
        )
    return org


@router.get("/{org_id}/integrations/erp360",
            response_model=Erp360IntegrationOut)
def get_erp360_integration(
    org_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_admin()),
):
    org = _load_org(db, current, org_id)
    s = org.erp360_settings
    return Erp360IntegrationOut(
        organization_id=org.id, organization_slug=org.slug,
        connected=org.is_erp360_connected,
        sso_enabled=org.erp360_sso_enabled,
        org_slug=s.get("org_slug"),
        billing_mode=s.get("billing_mode"),
        raw=s,
    )


class Erp360IntegrationPatch(BaseModel):
    connected: Optional[bool] = None
    sso_enabled: Optional[bool] = None
    org_slug: Optional[str] = Field(default=None, max_length=100)
    billing_mode: Optional[str] = Field(default=None, max_length=32)


_ALLOWED_BILLING_MODES = {"native_stripe", "erp360", None}


@router.patch("/{org_id}/integrations/erp360",
              response_model=Erp360IntegrationOut)
def patch_erp360_integration(
    org_id: int,
    body: Erp360IntegrationPatch,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_admin()),
):
    """Merge-update the org's ERP360 integration config. Only the
    fields present in the body are updated; anything else is
    preserved. Setting `org_slug=""` explicitly clears it.

    Rejects unknown `billing_mode` values so a typo can't silently
    break enrollment routing.
    """
    org = _load_org(db, current, org_id)

    if (body.billing_mode is not None and body.billing_mode != ""
            and body.billing_mode not in _ALLOWED_BILLING_MODES):
        raise HTTPException(
            status_code=400,
            detail=(
                f"billing_mode must be one of "
                f"{sorted(m for m in _ALLOWED_BILLING_MODES if m)} or null; "
                f"got {body.billing_mode!r}"
            ),
        )

    current_integrations = dict(org.integrations or {})
    current_erp360 = dict(current_integrations.get("erp360") or {})

    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        if v is None or v == "":
            current_erp360.pop(k, None)
        else:
            current_erp360[k] = v

    current_integrations["erp360"] = current_erp360
    org.integrations = current_integrations

    audit_service.record(
        db, current, "ORG_ERP360_INTEGRATION_UPDATED",
        target_type="organization", target_id=str(org.id),
        metadata={"changes": payload, "resulting_state": current_erp360},
        request=request,
    )
    db.commit()
    db.refresh(org)

    # Invalidate any per-org caches whose value would drift from the
    # newly-changed integration state.
    cache_delete(f"feature_flags:{org.id}")

    s = org.erp360_settings
    return Erp360IntegrationOut(
        organization_id=org.id, organization_slug=org.slug,
        connected=org.is_erp360_connected,
        sso_enabled=org.erp360_sso_enabled,
        org_slug=s.get("org_slug"),
        billing_mode=s.get("billing_mode"),
        raw=s,
    )
