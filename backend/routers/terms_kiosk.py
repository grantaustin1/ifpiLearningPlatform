"""Iter 30l — T&Cs versioning + kiosk mode + per-org feature flags.

Three logical surfaces, one router file for concision:

**T&Cs**
- `GET  /api/terms/current`      — public-ish (auth'd but org-scoped): fetch current version + whether current user has accepted
- `POST /api/terms/accept`       — record acceptance for the CURRENT version
- `GET  /api/admin/terms`        — list all versions (admin)
- `POST /api/admin/terms`        — publish a new version (flips previous current=False)
- `GET  /api/admin/terms/acceptances` — audit list of who accepted which version

**Kiosk**
- `GET  /api/kiosk/settings`     — read current org's kiosk config
- `PUT  /api/admin/kiosk/settings` — admin sets timeout / PIN / enabled
- `POST /api/kiosk/unlock`       — verify PIN (or password fallback) to unlock

**Feature flags**
- `GET  /api/feature-flags`      — resolved flag map for current org
- `PUT  /api/admin/feature-flags/{flag_key}` — admin set enabled

CSRF middleware and CSRF-exempt list unchanged — these are all
authenticated routes.
"""
from __future__ import annotations

import bcrypt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_admin
from core.database import get_db
from core.security import verify_password
from models import (
    FeatureFlag, KioskSettings, TermsAcceptance, TermsVersion, User,
)
from services import audit_service
from services.cache import cached_view, degrade_on_db_error, cache_delete

router = APIRouter(tags=["Terms & Kiosk"])


def _feature_flags_cache_key(
    response: Response = None, current: CurrentUser = None,
    db: Session = None, **_: object,
) -> str:
    org_id = getattr(current, "organization_id", "anon")
    return f"feature_flags:{org_id}"


# ── T&Cs schemas ──────────────────────────────────────────────────────


class TermsPublishIn(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    title: str = "Terms of Service"
    body_markdown: str = Field(default="")


class TermsAcceptIn(BaseModel):
    terms_version_id: int


# ── T&Cs read ─────────────────────────────────────────────────────────


@router.get("/api/terms/current")
def get_current_terms(current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    tv = (db.query(TermsVersion)
          .filter(TermsVersion.organization_id == current.organization_id,
                  TermsVersion.is_current.is_(True))
          .first())
    if not tv:
        return {"has_terms": False, "accepted": True}
    accepted = db.query(TermsAcceptance).filter(
        TermsAcceptance.user_id == current.id,
        TermsAcceptance.terms_version_id == tv.id,
    ).first() is not None
    return {
        "has_terms": True,
        "accepted": accepted,
        "terms": {
            "id": tv.id,
            "version": tv.version,
            "title": tv.title,
            "body_markdown": tv.body_markdown,
            "published_at": tv.published_at.isoformat(),
        },
    }


@router.post("/api/terms/accept")
def accept_terms(body: TermsAcceptIn, request: Request,
                 current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    tv = db.query(TermsVersion).filter(
        TermsVersion.id == body.terms_version_id,
        TermsVersion.organization_id == current.organization_id,
    ).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Terms version not found")
    existing = db.query(TermsAcceptance).filter(
        TermsAcceptance.user_id == current.id,
        TermsAcceptance.terms_version_id == tv.id,
    ).first()
    if existing:
        return {"accepted_at": existing.accepted_at.isoformat()}
    ip = (request.client.host if request.client else "") or ""
    ua = request.headers.get("user-agent", "")[:500]
    ack = TermsAcceptance(user_id=current.id, terms_version_id=tv.id,
                          ip_address=ip, user_agent=ua)
    db.add(ack)
    audit_service.record(db, current, "TERMS_ACCEPTED",
                         target_type="terms_version", target_id=str(tv.id),
                         metadata={"version": tv.version}, request=request)
    db.commit()
    db.refresh(ack)
    return {"accepted_at": ack.accepted_at.isoformat()}


# ── T&Cs admin ────────────────────────────────────────────────────────


@router.get("/api/admin/terms")
def list_terms(current: CurrentUser = Depends(requires_admin()),
               db: Session = Depends(get_db)):
    rows = (db.query(TermsVersion)
            .filter(TermsVersion.organization_id == current.organization_id)
            .order_by(TermsVersion.published_at.desc())
            .all())
    return {"items": [{
        "id": r.id, "version": r.version, "title": r.title,
        "body_markdown": r.body_markdown, "is_current": r.is_current,
        "published_at": r.published_at.isoformat(),
    } for r in rows]}


@router.post("/api/admin/terms")
def publish_terms(body: TermsPublishIn, request: Request,
                  current: CurrentUser = Depends(requires_admin()),
                  db: Session = Depends(get_db)):
    # Version string must be unique within org
    existing = db.query(TermsVersion).filter(
        TermsVersion.organization_id == current.organization_id,
        TermsVersion.version == body.version,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Version '{body.version}' already exists")
    # Flip all previous versions to non-current
    db.query(TermsVersion).filter(
        TermsVersion.organization_id == current.organization_id,
        TermsVersion.is_current.is_(True),
    ).update({"is_current": False})
    tv = TermsVersion(
        organization_id=current.organization_id,
        version=body.version, title=body.title,
        body_markdown=body.body_markdown, is_current=True,
        published_by_user_id=current.id,
    )
    db.add(tv)
    audit_service.record(db, current, "TERMS_PUBLISHED",
                         target_type="terms_version",
                         target_id=body.version, request=request)
    db.commit()
    db.refresh(tv)
    return {"id": tv.id, "version": tv.version,
            "published_at": tv.published_at.isoformat()}


@router.get("/api/admin/terms/acceptances")
def list_acceptances(limit: int = 200,
                     current: CurrentUser = Depends(requires_admin()),
                     db: Session = Depends(get_db)):
    q = (db.query(TermsAcceptance, User, TermsVersion)
         .join(User, User.id == TermsAcceptance.user_id)
         .join(TermsVersion, TermsVersion.id == TermsAcceptance.terms_version_id)
         .filter(TermsVersion.organization_id == current.organization_id)
         .order_by(TermsAcceptance.accepted_at.desc())
         .limit(min(max(limit, 1), 1000)))
    return {"items": [{
        "user_id": u.id, "email": u.email, "name": u.name,
        "version": tv.version, "accepted_at": ta.accepted_at.isoformat(),
        "ip_address": ta.ip_address,
    } for ta, u, tv in q.all()]}


# ── Kiosk ─────────────────────────────────────────────────────────────


class KioskSettingsIn(BaseModel):
    enabled: bool
    idle_timeout_seconds: int = Field(ge=0, le=3600)
    unlock_pin: Optional[str] = Field(default=None, min_length=4, max_length=10)


def _get_or_create_kiosk(db: Session, org_id: int) -> KioskSettings:
    row = db.query(KioskSettings).filter(
        KioskSettings.organization_id == org_id).first()
    if not row:
        row = KioskSettings(organization_id=org_id)
        db.add(row); db.flush()
    return row


@router.get("/api/kiosk/settings")
def get_kiosk_settings(current: CurrentUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    row = db.query(KioskSettings).filter(
        KioskSettings.organization_id == current.organization_id).first()
    if not row:
        return {"enabled": False, "idle_timeout_seconds": 300,
                "has_pin": False}
    return {"enabled": row.enabled,
            "idle_timeout_seconds": row.idle_timeout_seconds,
            "has_pin": bool(row.unlock_pin_hash)}


@router.put("/api/admin/kiosk/settings")
def update_kiosk_settings(body: KioskSettingsIn, request: Request,
                          current: CurrentUser = Depends(requires_admin()),
                          db: Session = Depends(get_db)):
    row = _get_or_create_kiosk(db, current.organization_id)
    row.enabled = body.enabled
    row.idle_timeout_seconds = body.idle_timeout_seconds
    if body.unlock_pin:
        row.unlock_pin_hash = bcrypt.hashpw(
            body.unlock_pin.encode(), bcrypt.gensalt(rounds=10)).decode()
    audit_service.record(db, current, "KIOSK_SETTINGS_UPDATED",
                         target_type="kiosk_settings",
                         target_id=str(row.id),
                         metadata={"enabled": body.enabled,
                                   "timeout": body.idle_timeout_seconds},
                         request=request)
    db.commit()
    return get_kiosk_settings(current, db)  # echo


class KioskUnlockIn(BaseModel):
    method: str = Field(pattern="^(pin|password)$")
    value: str = Field(min_length=1)


@router.post("/api/kiosk/unlock")
def kiosk_unlock(body: KioskUnlockIn,
                 current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if body.method == "pin":
        row = db.query(KioskSettings).filter(
            KioskSettings.organization_id == current.organization_id).first()
        if not row or not row.unlock_pin_hash:
            raise HTTPException(status_code=400,
                                detail="No kiosk PIN configured")
        if not bcrypt.checkpw(body.value.encode(),
                              row.unlock_pin_hash.encode()):
            raise HTTPException(status_code=401, detail="Incorrect PIN")
        return {"unlocked": True, "via": "pin"}
    # password fallback
    user = db.query(User).filter(User.id == current.id).first()
    if not user or not user.password_hash \
            or not verify_password(body.value, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"unlocked": True, "via": "password"}


# ── Feature flags ─────────────────────────────────────────────────────


class FeatureFlagIn(BaseModel):
    enabled: bool
    note: Optional[str] = None


# Registry of known flag keys with default enabled states.
KNOWN_FLAGS: dict[str, tuple[bool, str]] = {
    "ai_authoring":      (True,  "AI course + quiz builder suite"),
    "deep_research":     (True,  "Deep-research knowledge builder"),
    "sora_video":        (True,  "Sora 2 video slide generation"),
    "nano_banana":       (True,  "Nano Banana infographic slides"),
    "scorm_export":      (True,  "SCORM 1.2 / 2004 export"),
    "xapi_receiver":     (True,  "xAPI (Tin Can) receiver"),
    "webhooks_outgoing": (True,  "Outgoing HMAC-signed webhooks"),
    "api_tokens":        (True,  "External API tokens"),
    "kiosk_mode":        (False, "Public kiosk mode for shared devices"),
    "affiliate_program": (False, "Referral revenue-share program"),
    "marketplace":       (False, "Public course marketplace"),
    "live_sessions":     (False, "Live/webinar course sessions"),
}


@router.get("/api/feature-flags")
@cached_view(_feature_flags_cache_key, ttl_seconds=60.0)
@degrade_on_db_error(_feature_flags_cache_key)
def get_feature_flags(response: Response,
                      current: CurrentUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    rows = db.query(FeatureFlag).filter(
        FeatureFlag.organization_id == current.organization_id).all()
    overrides = {r.flag_key: r.enabled for r in rows}
    return {
        "flags": {
            key: overrides.get(key, default)
            for key, (default, _desc) in KNOWN_FLAGS.items()
        },
        "known_flags": [
            {"key": k, "default": d, "description": desc}
            for k, (d, desc) in KNOWN_FLAGS.items()
        ],
    }


@router.put("/api/admin/feature-flags/{flag_key}")
def set_feature_flag(flag_key: str, body: FeatureFlagIn, request: Request,
                     current: CurrentUser = Depends(requires_admin()),
                     db: Session = Depends(get_db)):
    if flag_key not in KNOWN_FLAGS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown flag_key '{flag_key}'. See /api/feature-flags for the registry.")
    row = db.query(FeatureFlag).filter(
        FeatureFlag.organization_id == current.organization_id,
        FeatureFlag.flag_key == flag_key,
    ).first()
    if not row:
        row = FeatureFlag(organization_id=current.organization_id,
                          flag_key=flag_key)
        db.add(row)
    row.enabled = body.enabled
    row.note = body.note
    audit_service.record(db, current, "FEATURE_FLAG_UPDATED",
                         target_type="feature_flag", target_id=flag_key,
                         metadata={"enabled": body.enabled}, request=request)
    db.commit()
    # Invalidate the per-org cache so the admin sees their change on next GET.
    cache_delete(f"feature_flags:{current.organization_id}")
    return {"flag_key": flag_key, "enabled": body.enabled,
            "note": body.note}
