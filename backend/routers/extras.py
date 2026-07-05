"""Extras: public lead capture, org branding update, outbox audit, path reorder."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from models import LearningPath, LearningPathItem, LifecycleStage, Organization, OutboxMessage, Person


# ── Lead capture (public — no auth) ───────────────────────────────────
leads_router = APIRouter(prefix="/api/leads", tags=["Leads"])


class LeadIn(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    source: Optional[str] = "embed"
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    country: Optional[str] = None
    organization_slug: Optional[str] = None    # which academy to attribute to


@leads_router.post("", status_code=201)
def capture_lead(body: LeadIn, db: Session = Depends(get_db)):
    """Public endpoint for partner sites / marketing pages to drop a lead in.

    Idempotent on (email, organization_id) — upserts the Person row and
    leaves an existing learner's lifecycle_stage untouched (won't downgrade).
    """
    org = None
    if body.organization_slug:
        org = db.query(Organization).filter(Organization.slug == body.organization_slug).first()
    if not org:
        org = db.query(Organization).order_by(Organization.id.asc()).first()
    if not org:
        raise HTTPException(status_code=500, detail="No academy configured")

    existing = db.query(Person).filter(
        Person.organization_id == org.id,
        Person.email == body.email.lower(),
    ).first()
    if existing:
        existing.updated_at = datetime.now(timezone.utc)
        if body.name and not existing.name: existing.name = body.name
        if body.phone: existing.phone = body.phone
        if body.company: existing.company = body.company
        if body.job_title: existing.job_title = body.job_title
        if body.country: existing.country = body.country
        # NEVER downgrade lifecycle
        if existing.lifecycle_stage == LifecycleStage.PROSPECT:
            existing.source = existing.source or body.source
        db.commit()
        return {"ok": True, "person_id": existing.id, "is_new": False,
                "lifecycle_stage": existing.lifecycle_stage.value}

    person = Person(
        organization_id=org.id, email=body.email.lower(), name=body.name,
        phone=body.phone, company=body.company, job_title=body.job_title,
        country=body.country, lifecycle_stage=LifecycleStage.PROSPECT,
        source=body.source or "embed",
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return {"ok": True, "person_id": person.id, "is_new": True,
            "lifecycle_stage": person.lifecycle_stage.value}


@leads_router.get("/embed.js")
def embed_widget(organization: Optional[str] = None,
                 redirect: Optional[str] = None):
    """Self-contained JS widget that partner sites drop on their page.

    Usage:
      <script src="https://learn.ifpi.org/api/leads/embed.js?organization=ifpi-main"
              data-redirect="https://yoursite.com/thanks"></script>
    """
    api_base = "/api/leads"
    js = f"""
(function() {{
  if (window.__IFPILeadEmbed) return;
  window.__IFPILeadEmbed = true;
  var scriptTag = document.currentScript;
  var orgSlug = {repr(organization or '')};
  var redirectUrl = scriptTag.getAttribute('data-redirect') || {repr(redirect or '')};
  var apiBase = scriptTag.src.replace(/\\/embed\\.js.*$/, '');

  var style = document.createElement('style');
  style.textContent = `
    .ifpi-lead-card {{ font-family: -apple-system, system-ui, sans-serif; max-width: 380px; background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 24px rgba(15,23,42,.08); border: 1px solid #e2e8f0; }}
    .ifpi-lead-card h3 {{ font-size: 16px; margin: 0 0 4px; color: #0f172a; }}
    .ifpi-lead-card p {{ font-size: 13px; color: #64748b; margin: 0 0 16px; }}
    .ifpi-lead-card input {{ width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 10px; font-size: 13px; margin-bottom: 8px; box-sizing: border-box; }}
    .ifpi-lead-card input:focus {{ outline: none; border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }}
    .ifpi-lead-card button {{ width: 100%; background: #6366f1; color: white; border: 0; padding: 10px; border-radius: 10px; font-weight: 600; font-size: 13px; cursor: pointer; }}
    .ifpi-lead-card button:disabled {{ opacity: .5; }}
    .ifpi-lead-card .ok {{ color: #10b981; font-size: 13px; margin-top: 8px; }}
    .ifpi-lead-card .err {{ color: #dc2626; font-size: 13px; margin-top: 8px; }}
  `;
  document.head.appendChild(style);

  var mountPoints = document.querySelectorAll('[data-ifpi-lead-form]');
  if (mountPoints.length === 0) {{
    var d = document.createElement('div'); d.setAttribute('data-ifpi-lead-form', ''); scriptTag.parentNode.insertBefore(d, scriptTag); mountPoints = [d];
  }}
  mountPoints.forEach(function(mount) {{
    var card = document.createElement('div'); card.className = 'ifpi-lead-card';
    card.innerHTML = '<h3>Get IFPI Learning updates</h3><p>Hear about new courses and learning paths.</p>' +
      '<input data-f="name" type="text" placeholder="Your name" />' +
      '<input data-f="email" type="email" placeholder="you@example.com" required />' +
      '<button>Subscribe</button><div class="msg"></div>';
    var btn = card.querySelector('button'), msg = card.querySelector('.msg');
    btn.addEventListener('click', function() {{
      var email = card.querySelector('[data-f=email]').value.trim();
      var name = card.querySelector('[data-f=name]').value.trim();
      if (!email) {{ msg.className='err'; msg.textContent='Email is required'; return; }}
      btn.disabled = true; msg.textContent='';
      fetch(apiBase, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ email: email, name: name, source: 'embed', organization_slug: orgSlug }})
      }}).then(function(r) {{ return r.ok ? r.json() : Promise.reject(r); }})
        .then(function() {{
          msg.className='ok';
          msg.textContent = "Thanks — we'll be in touch!";
          if (redirectUrl) setTimeout(function() {{ window.location.href = redirectUrl; }}, 800);
        }})
        .catch(function() {{ btn.disabled = false; msg.className='err'; msg.textContent='Something went wrong — please try again.'; }});
    }});
    mount.appendChild(card);
  }});
}})();
""".strip()
    return Response(content=js, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=300"})


# ── Organisation branding (admin) ─────────────────────────────────────
org_router = APIRouter(prefix="/api/organization", tags=["Organization"])


# ── Public branding (no auth — for login / signup pages, embed widgets) ──
# Returns ONLY the safe-to-display fields. Never returns SMTP config, budgets,
# or any auth-related data. Cached at edge for 5 min.
public_branding_router = APIRouter(prefix="/api/branding", tags=["Public Branding"])


@public_branding_router.get("/public")
def public_branding(slug: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch org branding by slug (query param). If no slug is passed, we
    return the FIRST org in the DB — sensible for single-tenant deployments
    like IFPI's initial rollout. The response is intentionally minimal:
    just brand name, logo URL, primary colour, accent colour."""
    from models import Organization
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
def list_theme_presets(current: CurrentUser = Depends(get_current_user)):
    """Read-only list of curated theme presets an ADMIN can apply in one click."""
    from services.theme_presets import PRESETS
    return PRESETS


@org_router.post("/apply-theme/{slug}")
def apply_theme_preset(slug: str, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
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


# ── Outbox (admin audit) ──────────────────────────────────────────────
outbox_router = APIRouter(prefix="/api/admin/outbox", tags=["Outbox"])


@outbox_router.get("")
def list_outbox(
    page: int = 1,
    page_size: int = 25,
    status: Optional[str] = None,
    template: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    query = db.query(OutboxMessage).filter(
        OutboxMessage.organization_id == current.organization_id,
    )
    if status:
        query = query.filter(OutboxMessage.status == status.upper())
    if template:
        query = query.filter(OutboxMessage.template == template)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (OutboxMessage.to_email.ilike(like)) | (OutboxMessage.subject.ilike(like)),
        )
    total = query.count()
    rows = query.order_by(OutboxMessage.created_at.desc())\
                .offset((page - 1) * page_size).limit(page_size).all()
    return {
        "messages": [{
            "id": m.id, "to_email": m.to_email, "to_name": m.to_name,
            "subject": m.subject, "template": m.template, "status": m.status,
            "transport": m.transport, "error": m.error,
            "attachments": m.attachments, "created_at": m.created_at,
            "sent_at": m.sent_at,
        } for m in rows],
        "page": page, "page_size": page_size, "total": total,
        "total_pages": (total + page_size - 1) // page_size if page_size else 1,
    }


@outbox_router.get("/stats")
def outbox_stats(db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    from sqlalchemy import func as sa_func
    rows = db.query(OutboxMessage.status, sa_func.count(OutboxMessage.id)).filter(
        OutboxMessage.organization_id == current.organization_id,
    ).group_by(OutboxMessage.status).all()
    return {status: count for status, count in rows}


@outbox_router.post("/{message_id}/retry")
def retry_outbox(message_id: int, db: Session = Depends(get_db),
                 current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    """Reset a FAILED or DEAD_LETTER message back to QUEUED so the worker
    picks it up on its next tick. Scoped to the caller's organization."""
    m = db.query(OutboxMessage).filter(
        OutboxMessage.id == message_id,
        OutboxMessage.organization_id == current.organization_id,
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    m.status = "QUEUED"
    m.attempt_count = 0
    m.next_attempt_at = None
    m.error = None
    db.commit()
    return {"ok": True, "id": m.id, "status": m.status}


# ── Learning path item reorder ────────────────────────────────────────
paths_extra_router = APIRouter(prefix="/api/learning-paths", tags=["Learning Paths"])


@paths_extra_router.patch("/{path_id}/items/reorder")
def reorder_path_items(path_id: int, body: dict, db: Session = Depends(get_db),
                       current: CurrentUser = Depends(requires_roles("INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Accepts {"item_ids": [id1, id2, ...]}."""
    p = db.query(LearningPath).filter(
        LearningPath.id == path_id,
        LearningPath.organization_id == current.organization_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Path not found")
    ids = body.get("item_ids") or []
    items = {i.id: i for i in p.items}
    for idx, iid in enumerate(ids, start=1):
        if iid in items:
            items[iid].order_index = idx
    db.commit()
    return {"ok": True, "count": len(ids)}
