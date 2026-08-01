from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.database import get_db
from models import Certificate

from . import cert_router


@cert_router.get("/verify/{code}")
def verify_certificate(code: str, db: Session = Depends(get_db)):
    from models import LiveSession
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    # Iter 27 — attendance certs surface the session title
    title = c.course.title if c.course else None
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        if sess:
            title = sess.title
    return {
        "valid": not bool(c.revoked_at),
        "code": c.code, "type": c.type,
        "recipient_name": c.user.name if c.user else None,
        "course_title": title,
        "issued_at": c.issued_at,
        # Iter 29 — revocation state (nulls when not revoked)
        "revoked_at": c.revoked_at,
        "revoked_reason": c.revoked_reason,
    }


@cert_router.get("/verify/{code}/og-image.svg", response_class=Response)
def certificate_og_image(code: str, db: Session = Depends(get_db)):
    """Iter 28 — SVG OG image for social share previews. 1200×630 to
    match Twitter/LinkedIn card ratios. Lightweight, static, safe to
    inline in HTML meta tags."""
    from models import LiveSession, Organization
    from xml.sax.saxutils import escape
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = f"Attended · {sess.title}" if sess else "Live Session Attendance"
    else:
        title = c.course.title if c.course else "IFPI Certificate"

    recipient = (c.user.name if c.user and c.user.name else "A learner")
    org_name = "IFPI Learning"
    if c.user and c.user.organization_id:
        org = db.query(Organization).filter(Organization.id == c.user.organization_id).first()
        if org:
            org_name = org.name

    # Truncate to avoid overflow
    def _fit(s: str, n: int) -> str:
        return s if len(s) <= n else s[:n - 1].rstrip() + "…"
    t = escape(_fit(title, 60))
    r = escape(_fit(recipient, 40))
    o = escape(_fit(org_name, 40))

    # Iter 29 — Revoked overlay
    revoked_overlay = ""
    if c.revoked_at:
        revoked_overlay = """
  <g opacity="0.92">
    <rect x="0" y="200" width="1200" height="120" fill="#dc2626" />
    <text x="600" y="278" text-anchor="middle"
          font-family="system-ui, -apple-system, Segoe UI, sans-serif"
          font-size="72" font-weight="800" fill="white"
          letter-spacing="8">REVOKED</text>
  </g>"""

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#eef2ff" />
      <stop offset="100%" stop-color="#ede9fe" />
    </linearGradient>
    <linearGradient id="ribbon" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1" />
      <stop offset="100%" stop-color="#8b5cf6" />
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)" />
  <rect x="60" y="80" width="1080" height="470" rx="24" fill="white" opacity="0.95" />
  <rect x="60" y="80" width="1080" height="8" fill="url(#ribbon)" />
  <text x="600" y="200" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="28" fill="#6366f1" font-weight="600">CERTIFICATE OF ACHIEVEMENT</text>
  <text x="600" y="290" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="52" fill="#1e293b" font-weight="700">{r}</text>
  <text x="600" y="360" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="22" fill="#64748b">has successfully completed</text>
  <text x="600" y="420" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="34" fill="#4338ca" font-weight="600">{t}</text>
  <text x="600" y="490" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif"
        font-size="18" fill="#94a3b8">Awarded by {o}</text>
  <text x="600" y="530" text-anchor="middle" font-family="ui-monospace, monospace"
        font-size="14" fill="#cbd5e1">verify: {escape(code)}</text>
{revoked_overlay}
</svg>"""
    return Response(svg, media_type="image/svg+xml", headers={
        # Iter 29 — revoked certs: shorter cache so LinkedIn re-fetches
        # sooner and reflects the revocation state in previews.
        "Cache-Control": "public, max-age=300" if c.revoked_at
                         else "public, max-age=86400",
    })
