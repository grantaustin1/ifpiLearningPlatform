from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import Organization

from . import org_router
from ._schemas import CohortSettingsIn, OrgUpdate, SmtpConfigIn, WebhookTestIn


@org_router.get("")
def get_org(db: Session = Depends(get_db),
            current: CurrentUser = Depends(get_current_user)) -> dict:
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
    }


@org_router.put("/cohort-settings")
def update_cohort_settings(body: CohortSettingsIn, db: Session = Depends(get_db),
                           current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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


def _detect_provider(url: str) -> str:
    u = (url or "").lower()
    if "discord.com/api/webhooks" in u or "discordapp.com/api/webhooks" in u:
        return "discord"
    if "hooks.slack.com" in u:
        return "slack"
    return "generic"


@org_router.post("/cohort-settings/test-webhook")
def test_cohort_webhook(body: WebhookTestIn, db: Session = Depends(get_db),
                        current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
                           current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
def list_theme_presets(current: CurrentUser = Depends(get_current_user)) -> list:
    """Read-only list of curated theme presets an ADMIN can apply in one click."""
    from services.theme_presets import PRESETS
    return PRESETS


@org_router.post("/apply-theme/{slug}")
def apply_theme_preset(slug: str, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
    """Copy a preset's branding values onto the caller's organization."""
    from services.theme_presets import get_preset
    preset = get_preset(slug)
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


@org_router.get("/smtp")
def get_smtp_config(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
                   current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
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
               current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))) -> dict:
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit()
    return {"ok": True}
