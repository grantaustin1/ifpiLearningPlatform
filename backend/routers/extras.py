"""Extras: public lead capture, org branding update, outbox audit, path reorder."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
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


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    description: Optional[str] = None


@org_router.get("")
def get_org(db: Session = Depends(get_db),
            current: CurrentUser = Depends(get_current_user)):
    o = db.query(Organization).filter(Organization.id == current.organization_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return {"id": o.id, "name": o.name, "slug": o.slug, "logo_url": o.logo_url,
            "primary_color": o.primary_color, "description": o.description,
            "status": o.status.value}


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
def list_outbox(limit: int = 50, db: Session = Depends(get_db),
                current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.query(OutboxMessage).filter(
        OutboxMessage.organization_id == current.organization_id,
    ).order_by(OutboxMessage.created_at.desc()).limit(limit).all()
    return [{
        "id": m.id, "to_email": m.to_email, "to_name": m.to_name,
        "subject": m.subject, "template": m.template, "status": m.status,
        "transport": m.transport, "error": m.error,
        "attachments": m.attachments, "created_at": m.created_at,
        "sent_at": m.sent_at,
    } for m in rows]


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
