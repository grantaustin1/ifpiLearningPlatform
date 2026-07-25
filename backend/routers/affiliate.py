"""Iter 30s — Affiliate / referral program.

Endpoints
---------
- `POST /api/admin/affiliate/codes`       — create a referral code
- `GET  /api/admin/affiliate/codes`       — list codes I own
- `PATCH /api/admin/affiliate/codes/{id}` — toggle active / update cap
- `GET  /api/admin/affiliate/referrals`   — who signed up via my codes
- `GET  /api/admin/affiliate/earnings`    — total credits pending / issued
- `GET  /api/affiliate/lookup/{code}`     — public preview (org name only)
- `POST /api/admin/affiliate/referrals/{id}/mark-credited` — SUPER_ADMIN
  operational endpoint to mark a referral as paid out. In prod this
  would be called by the billing worker on first-paid-invoice event.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_admin, requires_roles
from core.database import get_db
from models import AffiliateCode, AffiliateReferral, Organization
from services import audit_service

router = APIRouter(tags=["Affiliate"])


# ── Schemas ───────────────────────────────────────────────────────────


class CodeCreateIn(BaseModel):
    code: Optional[str] = Field(default=None, min_length=4, max_length=40)
    reward_bps: int = Field(default=1000, ge=100, le=5000)  # 1% – 50%
    cap_credits_cents: Optional[int] = Field(default=None, ge=100, le=1_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


class CodePatchIn(BaseModel):
    is_active: Optional[bool] = None
    cap_credits_cents: Optional[int] = Field(default=None, ge=100, le=1_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


# ── Helpers ───────────────────────────────────────────────────────────


def _generate_code(db: Session) -> str:
    """8-char case-preserving code (excludes ambiguous chars 0/O/l/1)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        candidate = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = db.query(AffiliateCode).filter(
            AffiliateCode.code == candidate).first()
        if not exists:
            return candidate
    raise RuntimeError("Could not generate unique code — try again")


def _serialize_code(c: AffiliateCode) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "reward_bps": c.reward_bps,
        "reward_pct": c.reward_bps / 100,
        "cap_credits_cents": c.cap_credits_cents,
        "is_active": c.is_active,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "note": c.note,
        "created_at": c.created_at.isoformat(),
    }


# ── Admin code management ─────────────────────────────────────────────


@router.post("/api/admin/affiliate/codes")
def create_code(body: CodeCreateIn, request: Request,
                current: CurrentUser = Depends(requires_admin()),
                db: Session = Depends(get_db)) -> dict:
    code = (body.code or _generate_code(db)).upper()
    # Uniqueness check
    if db.query(AffiliateCode).filter(AffiliateCode.code == code).first():
        raise HTTPException(status_code=409, detail=f"Code '{code}' already exists")
    row = AffiliateCode(
        organization_id=current.organization_id,
        code=code,
        reward_bps=body.reward_bps,
        cap_credits_cents=body.cap_credits_cents,
        note=body.note,
        created_by_user_id=current.id,
    )
    db.add(row)
    audit_service.record(db, current, "AFFILIATE_CODE_CREATED",
                         target_type="affiliate_code", target_id=None,
                         metadata={"code": code, "reward_bps": body.reward_bps},
                         request=request)
    db.commit(); db.refresh(row)
    return _serialize_code(row)


@router.get("/api/admin/affiliate/codes")
def list_codes(current: CurrentUser = Depends(requires_admin()),
               db: Session = Depends(get_db)) -> dict:
    rows = (db.query(AffiliateCode)
            .filter(AffiliateCode.organization_id == current.organization_id)
            .order_by(AffiliateCode.created_at.desc()).all())
    return {"items": [_serialize_code(r) for r in rows]}


@router.patch("/api/admin/affiliate/codes/{code_id}")
def update_code(code_id: int, body: CodePatchIn, request: Request,
                current: CurrentUser = Depends(requires_admin()),
                db: Session = Depends(get_db)) -> dict:
    row = db.query(AffiliateCode).filter(
        AffiliateCode.id == code_id,
        AffiliateCode.organization_id == current.organization_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Code not found")
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.cap_credits_cents is not None:
        row.cap_credits_cents = body.cap_credits_cents
    if body.note is not None:
        row.note = body.note
    audit_service.record(db, current, "AFFILIATE_CODE_UPDATED",
                         target_type="affiliate_code", target_id=str(code_id),
                         request=request)
    db.commit()
    return _serialize_code(row)


# ── Referral tracking ─────────────────────────────────────────────────


@router.get("/api/admin/affiliate/referrals")
def list_referrals(current: CurrentUser = Depends(requires_admin()),
                   db: Session = Depends(get_db)) -> dict:
    """Referrals attributed to codes I own."""
    q = (db.query(AffiliateReferral, AffiliateCode, Organization)
         .join(AffiliateCode, AffiliateCode.id == AffiliateReferral.code_id)
         .join(Organization, Organization.id == AffiliateReferral.referred_organization_id)
         .filter(AffiliateCode.organization_id == current.organization_id)
         .order_by(AffiliateReferral.signed_up_at.desc()))
    return {"items": [{
        "id": ref.id, "code": code.code,
        "referred_org_id": org.id,
        "referred_org_name": org.name,
        "signed_up_at": ref.signed_up_at.isoformat(),
        "status": ref.status,
        "credit_cents": ref.credit_cents,
        "credited_at": ref.credited_at.isoformat() if ref.credited_at else None,
        "notes": ref.notes,
    } for ref, code, org in q.all()]}


@router.get("/api/admin/affiliate/earnings")
def earnings(current: CurrentUser = Depends(requires_admin()),
             db: Session = Depends(get_db)) -> dict:
    """Aggregate earnings by status. Cents-based to avoid float drift."""
    q = (db.query(AffiliateReferral.status,
                  func.count(AffiliateReferral.id).label("count"),
                  func.coalesce(func.sum(AffiliateReferral.credit_cents), 0).label("cents"))
         .join(AffiliateCode, AffiliateCode.id == AffiliateReferral.code_id)
         .filter(AffiliateCode.organization_id == current.organization_id)
         .group_by(AffiliateReferral.status))
    by_status = {status: {"count": count, "cents": int(cents)}
                 for status, count, cents in q.all()}
    total_credited = by_status.get("CREDITED", {}).get("cents", 0)
    total_pending = by_status.get("PENDING", {}).get("cents", 0) or 0
    return {
        "total_credited_cents": total_credited,
        "total_pending_cents": total_pending,
        "by_status": by_status,
    }


# ── Public code lookup (used during registration) ────────────────────


@router.get("/api/affiliate/lookup/{code}")
def lookup(code: str, db: Session = Depends(get_db)) -> dict:
    """Public — thin preview so signup forms can show
    'You're being referred by ACME Corp'. Does NOT return internal ids."""
    row = (db.query(AffiliateCode, Organization)
           .join(Organization, Organization.id == AffiliateCode.organization_id)
           .filter(AffiliateCode.code == code.upper(),
                   AffiliateCode.is_active.is_(True)).first())
    if not row:
        raise HTTPException(status_code=404, detail="Code not found or inactive")
    _code, org = row
    if _code.expires_at and _code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Code expired")
    return {"valid": True, "referrer_org_name": org.name}


# ── Referral marking (billing/SUPER_ADMIN op) ────────────────────────


class MarkCreditedIn(BaseModel):
    credit_cents: int = Field(ge=100, le=1_000_000)
    notes: Optional[str] = Field(default=None, max_length=500)


@router.post("/api/admin/affiliate/referrals/{referral_id}/mark-credited")
def mark_credited(referral_id: int, body: MarkCreditedIn, request: Request,
                  current: CurrentUser = Depends(requires_roles("SUPER_ADMIN")),
                  db: Session = Depends(get_db)) -> dict:
    ref = db.query(AffiliateReferral).filter(
        AffiliateReferral.id == referral_id).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")
    if ref.status == "CREDITED":
        return {"already_credited": True, "credited_at": ref.credited_at.isoformat()}
    ref.credit_cents = body.credit_cents
    ref.status = "CREDITED"
    ref.credited_at = datetime.utcnow()
    ref.notes = body.notes
    audit_service.record(db, current, "AFFILIATE_REFERRAL_CREDITED",
                         target_type="affiliate_referral",
                         target_id=str(referral_id),
                         metadata={"credit_cents": body.credit_cents},
                         request=request)
    db.commit()
    return {"credited": True, "credit_cents": ref.credit_cents}


# ── Attribution helper (used by register endpoint) ───────────────────


def attribute_signup(db: Session, code_str: str,
                     new_org_id: int) -> Optional[AffiliateReferral]:
    """Called during org registration when ?ref=CODE is present.
    Returns the created referral row, or None on validation failure."""
    if not code_str:
        return None
    code = db.query(AffiliateCode).filter(
        AffiliateCode.code == code_str.upper(),
        AffiliateCode.is_active.is_(True)).first()
    if not code:
        return None
    if code.expires_at and code.expires_at < datetime.utcnow():
        return None
    # Anti-fraud: can't self-refer
    if code.organization_id == new_org_id:
        return None
    # Idempotent: already referred
    existing = db.query(AffiliateReferral).filter(
        AffiliateReferral.code_id == code.id,
        AffiliateReferral.referred_organization_id == new_org_id).first()
    if existing:
        return existing
    ref = AffiliateReferral(
        code_id=code.id,
        referred_organization_id=new_org_id,
    )
    db.add(ref); db.flush()
    return ref
