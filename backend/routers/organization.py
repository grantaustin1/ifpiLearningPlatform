"""Organization router — branding, SMTP, cohort/nurture settings, themes."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import CustomThemePreset, Organization


# ── Public branding (no auth — for login / signup pages, embed widgets) ──
public_branding_router = APIRouter(prefix="/api/branding", tags=["Public Branding"])


@public_branding_router.get("/public")
def public_branding(slug: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch org branding by slug (query param). If no slug is passed, we
    return the FIRST org in the DB — sensible for single-tenant deployments
    like IFPI's initial rollout. The response is intentionally minimal:
    just brand name, logo URL, primary colour, accent colour."""
    q = db.query(Organization)
    if slug:
        q = q.filter(Organization.slug == slug)
    else:
        q = q.order_by(Organization.id.asc())
    org = q.first()
    if not org:
        return {"name": "Learning Platform", "logo_url": None,
                "primary_color": "#6366f1", "accent_color": "#F5A500",
                "slug": None}
    return {
        "name": org.name,
        "slug": org.slug,
        "logo_url": org.logo_url,
        "primary_color": org.primary_color or "#6366f1",
        "accent_color": org.cert_accent_color or org.primary_color or "#F5A500",
    }


# ── Organisation branding (admin) ─────────────────────────────────────
org_router = APIRouter(prefix="/api/organization", tags=["Organization"])


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    description: Optional[str] = None
    cert_accent_color: Optional[str] = None
    cert_signature_text: Optional[str] = None
    cert_signature_image_url: Optional[str] = None
    cert_footer_text: Optional[str] = None
    marketplace_opt_in: Optional[bool] = None


@org_router.get("")
def get_org(db: Session = Depends(get_db),
            current: CurrentUser = Depends(get_current_user)):
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return {
        "id": o.id, "name": o.name, "slug": o.slug, "logo_url": o.logo_url,
        "primary_color": o.primary_color, "description": o.description,
        "status": o.status.value,
        "cert_accent_color": o.cert_accent_color,
        "cert_signature_text": o.cert_signature_text,
        "cert_signature_image_url": o.cert_signature_image_url,
        "cert_footer_text": o.cert_footer_text,
        "theme_preset": o.theme_preset,
        "cohort_threshold": o.cohort_threshold or 75,
        "cohort_celebration_webhook_url": o.cohort_celebration_webhook_url,
        "cohort_digest_enabled": bool(o.cohort_digest_enabled) if o.cohort_digest_enabled is not None else True,
        "cohort_digest_last_sent_at": o.cohort_digest_last_sent_at.isoformat() if o.cohort_digest_last_sent_at else None,
        "marketplace_opt_in": bool(o.marketplace_opt_in) if o.marketplace_opt_in is not None else True,
        "nurture_enabled": bool(o.nurture_enabled),
        "nurture_days": o.nurture_days or 3,
        "nurture_message": o.nurture_message,
        "nurture_second_enabled": bool(o.nurture_second_enabled),
        "nurture_second_days": o.nurture_second_days or 7,
    }


class CohortSettingsIn(BaseModel):
    cohort_threshold: int = Field(ge=1, le=100, default=75)
    cohort_celebration_webhook_url: Optional[str] = None
    cohort_digest_enabled: Optional[bool] = None  # None = leave unchanged


@org_router.put("/cohort-settings")
def update_cohort_settings(body: CohortSettingsIn, db: Session = Depends(get_db),
                           current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    o.cohort_threshold = body.cohort_threshold
    o.cohort_celebration_webhook_url = (body.cohort_celebration_webhook_url or "").strip() or None
    if body.cohort_digest_enabled is not None:
        o.cohort_digest_enabled = bool(body.cohort_digest_enabled)
    from services import audit_service
    audit_service.record(db, current, "COHORT_SETTINGS_UPDATED",
        target_type="organization", target_id=str(o.id),
        metadata={"threshold": body.cohort_threshold,
                  "webhook": bool(o.cohort_celebration_webhook_url),
                  "digest_enabled": bool(o.cohort_digest_enabled)})
    db.commit()
    return {"ok": True}


class WebhookTestIn(BaseModel):
    webhook_url: str = Field(min_length=8, max_length=500)


class NurtureSettingsIn(BaseModel):
    nurture_enabled: bool = False
    nurture_days: int = Field(ge=1, le=30, default=3)
    nurture_message: Optional[str] = None
    nurture_second_enabled: bool = False
    nurture_second_days: int = Field(ge=1, le=60, default=7)


@org_router.put("/nurture-settings")
def update_nurture_settings(body: NurtureSettingsIn, db: Session = Depends(get_db),
                            current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    o.nurture_enabled = body.nurture_enabled
    o.nurture_days = body.nurture_days
    o.nurture_message = (body.nurture_message or "").strip() or None
    o.nurture_second_enabled = body.nurture_second_enabled
    o.nurture_second_days = body.nurture_second_days
    from services import audit_service
    audit_service.record(db, current, "NURTURE_SETTINGS_UPDATED",
        target_type="organization", target_id=str(o.id),
        metadata={"enabled": body.nurture_enabled, "days": body.nurture_days})
    db.commit()
    return {"ok": True}


@org_router.post("/nurture-settings/run-now")
def run_nurture_now(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    from services.nurture_service import run_nurture_pass
    sent = run_nurture_pass(db, org_id=current.organization_id)
    return {"ok": True, "nudges_sent": sent}


def _detect_provider(url: str) -> str:
    u = (url or "").lower()
    if "discord.com/api/webhooks" in u or "discordapp.com/api/webhooks" in u:
        return "discord"
    if "hooks.slack.com" in u:
        return "slack"
    return "generic"


@org_router.post("/cohort-settings/test-webhook")
def test_cohort_webhook(body: WebhookTestIn, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Send a sample celebration message to verify the configured webhook.

    Returns the upstream HTTP status so the admin sees whether Discord/Slack
    accepted the payload. Records an audit row either way.
    """
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")

    url = (body.webhook_url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=422, detail="Webhook URL must start with http:// or https://")

    provider = _detect_provider(url)
    sample_text = (
        f"🎉 *{o.name}* — Test celebration ping from IFPI Learning. "
        f"If you can see this, your milestone webhook is wired correctly."
    )
    status_code: Optional[int] = None
    ok = False
    err: Optional[str] = None
    try:
        import requests as _r
        resp = _r.post(url, json={
            "text": sample_text,
            "content": sample_text,
            "username": "IFPI Learning",
        }, timeout=8)
        status_code = resp.status_code
        ok = 200 <= resp.status_code < 300
        if not ok:
            err = (resp.text or "")[:300]
    except Exception as e:  # network / DNS / timeout
        err = f"{type(e).__name__}: {e}"[:300]

    from services import audit_service
    audit_service.record(db, current, "COHORT_WEBHOOK_TESTED",
        target_type="organization", target_id=str(o.id),
        metadata={"provider": provider, "status_code": status_code, "ok": ok,
                  "error": err})
    db.commit()
    return {"ok": ok, "status_code": status_code, "provider": provider, "error": err}


@org_router.post("/cohort-digest/send-now")
def send_cohort_digest_now(db: Session = Depends(get_db),
                           current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Manual trigger — queues the weekly cohort digest immediately for this
    org. Unlike the scheduled job this ignores the 6-day dedupe window so an
    admin can preview the email on demand.
    """
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    from services.cohort_digest import send_digest_for_org, compute_org_digest
    queued = send_digest_for_org(db, o, actor=current)
    db.commit()
    preview = compute_org_digest(db, o)
    return {
        "queued": queued,
        "total_cohorts": preview["total_cohorts"],
        "past": len(preview["past"]),
        "nudge": len(preview["nudge"]),
        "threshold": preview["threshold"],
    }


@org_router.get("/themes")
def list_theme_presets(db: Session = Depends(get_db),
                       current: CurrentUser = Depends(get_current_user)):
    """Built-in presets + this org's custom presets (marked `custom: true`)."""
    from services.theme_presets import PRESETS
    custom = (db.query(CustomThemePreset)
              .filter(CustomThemePreset.organization_id == current.organization_id)
              .order_by(CustomThemePreset.created_at).all())
    return [dict(p, custom=False) for p in PRESETS] + [{
        "id": c.id, "slug": c.slug, "name": c.name,
        "description": c.description or "",
        "primary_color": c.primary_color,
        "cert_accent_color": c.cert_accent_color,
        "cert_signature_text_suggestion": c.cert_signature_text_suggestion or "",
        "cert_footer_text_suggestion": c.cert_footer_text_suggestion or "",
        "cover_color": c.cover_color or "bg-indigo-500",
        "custom": True,
    } for c in custom]


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ThemePresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    primary_color: str = "#6366f1"
    cert_accent_color: str = "#6366f1"
    cert_signature_text_suggestion: Optional[str] = Field(default=None, max_length=200)
    cert_footer_text_suggestion: Optional[str] = None


def _validate_theme_body(body: ThemePresetIn) -> None:
    for field in ("primary_color", "cert_accent_color"):
        if not _HEX_RE.match(getattr(body, field) or ""):
            raise HTTPException(status_code=422,
                                detail=f"{field} must be a hex colour like #1e293b")


def _get_custom_preset(db: Session, current: CurrentUser, preset_id: int) -> "CustomThemePreset":
    row = (db.query(CustomThemePreset)
           .filter(CustomThemePreset.id == preset_id,
                   CustomThemePreset.organization_id == current.organization_id)
           .first())
    if not row:
        raise HTTPException(status_code=404, detail="Custom theme preset not found")
    return row


@org_router.post("/themes", status_code=201)
def create_custom_theme(body: ThemePresetIn, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Create a custom theme preset for the caller's organization."""
    from services.theme_presets import PRESETS
    _validate_theme_body(body)
    base_slug = re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_") or "custom"
    slug, n = f"custom_{base_slug}", 2
    taken = ({p["slug"] for p in PRESETS} |
             {c.slug for c in db.query(CustomThemePreset)
              .filter(CustomThemePreset.organization_id == current.organization_id).all()})
    while slug in taken:
        slug, n = f"custom_{base_slug}_{n}", n + 1
    row = CustomThemePreset(
        organization_id=current.organization_id, slug=slug, name=body.name,
        description=body.description,
        primary_color=body.primary_color, cert_accent_color=body.cert_accent_color,
        cert_signature_text_suggestion=body.cert_signature_text_suggestion,
        cert_footer_text_suggestion=body.cert_footer_text_suggestion,
    )
    db.add(row)
    db.commit()
    return {"ok": True, "id": row.id, "slug": row.slug}


@org_router.put("/themes/{preset_id}")
def update_custom_theme(preset_id: int, body: ThemePresetIn,
                        db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Update a custom theme preset (org-scoped)."""
    _validate_theme_body(body)
    row = _get_custom_preset(db, current, preset_id)
    row.name = body.name
    row.description = body.description
    row.primary_color = body.primary_color
    row.cert_accent_color = body.cert_accent_color
    row.cert_signature_text_suggestion = body.cert_signature_text_suggestion
    row.cert_footer_text_suggestion = body.cert_footer_text_suggestion
    db.commit()
    return {"ok": True, "id": row.id, "slug": row.slug}


@org_router.delete("/themes/{preset_id}")
def delete_custom_theme(preset_id: int, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Delete a custom theme preset. Orgs currently using it keep their
    applied colours (values were copied at apply time)."""
    row = _get_custom_preset(db, current, preset_id)
    db.delete(row)
    db.commit()
    return {"ok": True}


@org_router.post("/apply-theme/{slug}")
def apply_theme_preset(slug: str, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Copy a preset's branding values onto the caller's organization.
    Looks up built-ins first, then the org's custom presets."""
    from services.theme_presets import get_preset
    preset = get_preset(slug)
    if not preset:
        row = (db.query(CustomThemePreset)
               .filter(CustomThemePreset.slug == slug,
                       CustomThemePreset.organization_id == current.organization_id)
               .first())
        if row:
            preset = {
                "slug": row.slug,
                "primary_color": row.primary_color,
                "cert_accent_color": row.cert_accent_color,
                "cert_signature_text_suggestion": row.cert_signature_text_suggestion or "",
                "cert_footer_text_suggestion": row.cert_footer_text_suggestion or "",
            }
    if not preset:
        raise HTTPException(status_code=404, detail="Theme preset not found")
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    o.primary_color = preset["primary_color"]
    o.cert_accent_color = preset["cert_accent_color"]
    # Only seed the text fields if they are still empty — never overwrite
    # admin-customised copy.
    if not (o.cert_signature_text or "").strip():
        o.cert_signature_text = preset["cert_signature_text_suggestion"]
    if not (o.cert_footer_text or "").strip():
        o.cert_footer_text = preset["cert_footer_text_suggestion"]
    o.theme_preset = preset["slug"]
    from services import audit_service
    audit_service.record(db, current, "THEME_APPLIED",
        target_type="organization", target_id=str(o.id),
        metadata={"preset": preset["slug"]})
    db.commit()
    return {"ok": True, "applied": preset["slug"]}


# ── Per-tenant SMTP overrides ────────────────────────────────────────
class SmtpConfigIn(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # plain in transit, encrypted at rest
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: bool = True


@org_router.get("/smtp")
def get_smtp_config(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Returns the SMTP config minus the password. Password is write-only."""
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return {
        "smtp_host": o.smtp_host, "smtp_port": o.smtp_port,
        "smtp_username": o.smtp_username, "smtp_from_email": o.smtp_from_email,
        "smtp_from_name": o.smtp_from_name, "smtp_use_tls": o.smtp_use_tls,
        "has_password": bool(o.smtp_password_enc),
        "is_configured": bool(o.smtp_host and o.smtp_from_email),
    }


@org_router.put("/smtp")
def update_smtp_config(body: SmtpConfigIn, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    from services.smtp_service import encrypt_password
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    o.smtp_host = body.smtp_host
    o.smtp_port = body.smtp_port
    o.smtp_username = body.smtp_username
    if body.smtp_password is None:
        pass  # leave existing password alone
    elif body.smtp_password == "":
        o.smtp_password_enc = None  # explicit clear
    else:
        o.smtp_password_enc = encrypt_password(body.smtp_password)
    o.smtp_from_email = body.smtp_from_email
    o.smtp_from_name = body.smtp_from_name
    o.smtp_use_tls = body.smtp_use_tls
    from services import audit_service
    audit_service.record(db, current, "SMTP_CONFIG_UPDATED",
        target_type="organization", target_id=str(o.id),
        metadata={"host": o.smtp_host, "from": o.smtp_from_email})
    db.commit()
    return {"ok": True}


@org_router.post("/smtp/test")
def test_smtp_send(body: dict, db: Session = Depends(get_db),
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Send a test email immediately (synchronous, NOT via the outbox)."""
    from services.smtp_service import send_via_org_smtp
    to = (body.get("to") or "").strip()
    if not to:
        raise HTTPException(status_code=400, detail="`to` email required")
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o or not o.smtp_host or not o.smtp_from_email:
        raise HTTPException(status_code=400, detail="SMTP not configured")
    try:
        send_via_org_smtp(
            host=o.smtp_host, port=o.smtp_port or 587,
            username=o.smtp_username, password_enc=o.smtp_password_enc,
            use_tls=o.smtp_use_tls if o.smtp_use_tls is not None else True,
            from_email=o.smtp_from_email, from_name=o.smtp_from_name,
            to_email=to, to_name=None, subject=f"[{o.name}] SMTP test from IFPI",
            body_html=f"<p>This is a test email from <strong>{o.name}</strong> on IFPI Learning. If you got this, your SMTP is working.</p>",
            body_text=f"This is a test email from {o.name} on IFPI Learning.",
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP test failed: {str(e)[:300]}")


@org_router.patch("")
def update_org(body: OrgUpdate, db: Session = Depends(get_db),
               current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit()
    return {"ok": True}
