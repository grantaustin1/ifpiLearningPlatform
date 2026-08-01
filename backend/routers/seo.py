"""Iter 28 — Public SEO endpoints.

Serves:
- `GET /sitemap.xml`            — Global sitemap of all opted-in orgs +
                                  all published courses.
- `GET /sitemap-{org_id}.xml`   — Per-org sitemap with that org's
                                  published courses only.
- `GET /robots.txt`             — Public robots policy pointing to the
                                  global sitemap.
- `GET /certificates/share/{code}` — Server-rendered HTML brag-card
                                     with OpenGraph + Twitter meta
                                     tags so LinkedIn/Twitter/WhatsApp
                                     link previews look great.

These routes DELIBERATELY sit OUTSIDE the `/api` prefix — search
engines and social crawlers won't respect an `/api/sitemap.xml`.
"""
from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from core.database import get_db
from models import Certificate, Course, CourseStatus, LiveSession, Organization

# NB: prefixed with `/api/seo` so the K8s ingress routes correctly to
# the backend. A static robots.txt in `/app/frontend/public/robots.txt`
# points crawlers to `/api/seo/sitemap.xml`, which is fully crawler-
# discoverable — LinkedIn / Twitter / Google crawlers do not
# discriminate against API-prefixed URLs.
router = APIRouter(prefix="/api/seo", tags=["SEO"])


# ─────────────────────────── Sitemap helpers ─────────────────────────
def _base(req: Request) -> str:
    """Iter 29 — Prefer the `PUBLIC_BASE_URL` env var so preview
    environments emit the public preview hostname (e.g.
<<<<<<< HEAD
    `https://last-checkpoint-15.preview.emergentagent.com`) rather than the K8s
=======
    `https://foo.preview.emergentagent.com`) rather than the K8s
>>>>>>> origin/main
    cluster-internal hostname derived from the ingress `Host` header.
    Falls back to `request.base_url` in dev/prod when the env var is
    unset."""
    override = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if override:
        return override
    return str(req.base_url).rstrip("/")


def _sitemap_xml(urls: list[dict]) -> str:
    now = datetime.now(timezone.utc).date().isoformat()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        parts.append("<url>")
        parts.append(f"<loc>{escape(u['loc'])}</loc>")
        parts.append(f"<lastmod>{u.get('lastmod', now)}</lastmod>")
        parts.append(f"<changefreq>{u.get('changefreq', 'weekly')}</changefreq>")
        parts.append(f"<priority>{u.get('priority', '0.6')}</priority>")
        parts.append("</url>")
    parts.append("</urlset>")
    return "\n".join(parts)


@router.get("/robots.txt", response_class=Response)
def robots_txt(request: Request):
    body = (
        "User-agent: *\n"
        "Allow: /catalog\n"
        "Allow: /verify\n"
        "Allow: /api/seo/certificates/share\n"
        "Disallow: /api/\n"
        "Disallow: /dashboard\n"
        "Disallow: /admin\n"
        f"Sitemap: {_base(request)}/api/seo/sitemap.xml\n"
    )
    return Response(body, media_type="text/plain")


@router.get("/sitemap.xml", response_class=Response)
def sitemap_root(request: Request, db: Session = Depends(get_db)):
    base = _base(request)
    urls = [
        {"loc": base + "/", "priority": "1.0", "changefreq": "daily"},
        {"loc": base + "/catalog", "priority": "0.9", "changefreq": "daily"},
    ]
    # Global public courses (aggregated across opted-in orgs)
    courses = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .limit(5000)  # sitemaps must be <= 50k URLs; be conservative
        .all()
    )
    for c in courses:
        urls.append({
            "loc": f"{base}/catalog/{c.id}",
            "priority": "0.7",
            "changefreq": "weekly",
        })
    # Per-org sitemap references (crawler-friendly)
    orgs = db.query(Organization).filter(
        Organization.marketplace_opt_in == True,  # noqa: E712
    ).all()
    for o in orgs:
        urls.append({
            "loc": f"{base}/api/seo/sitemap-{o.id}.xml",
            "priority": "0.5",
            "changefreq": "weekly",
        })
    return Response(_sitemap_xml(urls), media_type="application/xml")


@router.get("/sitemap-{org_id}.xml", response_class=Response)
def sitemap_org(org_id: int, request: Request, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(
        Organization.id == org_id,
        Organization.marketplace_opt_in == True,  # noqa: E712
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found or not public")
    base = _base(request)
    urls = [{"loc": f"{base}/catalog?org={org_id}", "priority": "0.8",
             "changefreq": "daily"}]
    courses = db.query(Course).filter(
        Course.organization_id == org_id,
        Course.status == CourseStatus.PUBLISHED,
    ).all()
    for c in courses:
        urls.append({"loc": f"{base}/catalog/{c.id}", "priority": "0.7"})
    return Response(_sitemap_xml(urls), media_type="application/xml")


# ───────────── Certificate share (brag card / OG preview) ────────────
def _og_meta(title: str, description: str, image_url: str, url: str) -> str:
    """Compact set of Twitter + OpenGraph meta tags for crisp social
    previews. Also renders a graceful HTML fallback so humans opening
    the URL see the same info."""
    e_title = html.escape(title)
    e_desc = html.escape(description)
    e_url = html.escape(url)
    e_img = html.escape(image_url)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{e_title}</title>
  <meta name="description" content="{e_desc}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{e_title}" />
  <meta property="og:description" content="{e_desc}" />
  <meta property="og:image" content="{e_img}" />
  <meta property="og:url" content="{e_url}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{e_title}" />
  <meta name="twitter:description" content="{e_desc}" />
  <meta name="twitter:image" content="{e_img}" />
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: linear-gradient(135deg, #eef2ff 0%, #ede9fe 100%);
      min-height: 100vh; margin: 0; display: flex;
      align-items: center; justify-content: center; padding: 24px; }}
    .card {{ background: white; border-radius: 24px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.08);
      padding: 40px; max-width: 640px; text-align: center; }}
    .card h1 {{ font-size: 28px; margin: 0 0 8px; color: #4f46e5; }}
    .card p.recipient {{ font-size: 20px; margin: 24px 0 8px;
      font-weight: 600; color: #1e293b; }}
    .card p.subtitle {{ font-size: 14px; color: #64748b; margin: 0 0 24px; }}
    .card .cta a {{ display: inline-block; background: #4f46e5;
      color: white; padding: 12px 24px; border-radius: 12px;
      text-decoration: none; font-weight: 600; font-size: 14px; }}
    .card .cta a.secondary {{ background: white; color: #4f46e5;
      margin-left: 8px; border: 1px solid #e2e8f0; }}
    img.logo {{ max-height: 40px; margin-bottom: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{e_title}</h1>
    <p class="subtitle">Verified certificate</p>
    <p class="recipient">{e_desc}</p>
    <div class="cta">
      <a href="/verify/{{code}}">Verify certificate</a>
      <a class="secondary" href="/catalog">Explore courses</a>
    </div>
  </div>
</body>
</html>"""


@router.get("/certificates/share/{code}", response_class=Response)
def cert_share(code: str, request: Request, db: Session = Depends(get_db)):
    """Iter 28 — Public shareable brag-card for a certificate.

    Fetched by LinkedIn/Twitter/WhatsApp when a learner posts the URL.
    Renders a compact HTML page with OpenGraph meta tags for a rich
    link preview + a fallback human-readable card."""
    c = db.query(Certificate).filter(Certificate.code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Resolve title
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id:
        sess = db.query(LiveSession).filter(LiveSession.id == c.live_session_id).first()
        title = f"Attended: {sess.title}" if sess else "Attended a live session"
    else:
        title = c.course.title if c.course else "IFPI Certificate"

    recipient = c.user.name if c.user and c.user.name else "A learner"
    org_name = "IFPI Learning"
    if c.user and c.user.organization_id:
        org = db.query(Organization).filter(Organization.id == c.user.organization_id).first()
        if org:
            org_name = org.name

    base = _base(request)
    share_url = f"{base}/api/seo/certificates/share/{code}"
    # Pre-baked SVG OG image (light-weight, always renders)
    og_image = f"{base}/api/certificates/verify/{code}/og-image.svg"

    # Iter 29 — Revoked certs get a different title/desc so LinkedIn's
    # link preview reflects the invalidation on next crawl.
    revoked = c.revoked_at is not None
    if revoked:
        header_title = f"[REVOKED] {recipient} · {title}"
        header_desc = f"This certificate has been revoked by {org_name}"
    else:
        header_title = f"{recipient} · {title}"
        header_desc = f"Awarded by {org_name}"

    html_body = _og_meta(
        title=header_title,
        description=header_desc,
        image_url=og_image,
        url=share_url,
    ).replace("{code}", html.escape(code))
    # Inject a red REVOKED ribbon at the top of the human-visible card
    if revoked:
        html_body = html_body.replace(
            '<div class="card">',
            '<div class="card" style="border:2px solid #dc2626;position:relative;">'
            '<div style="position:absolute;top:-1px;left:-1px;right:-1px;'
            'background:#dc2626;color:white;font-weight:700;padding:8px;'
            'font-size:13px;letter-spacing:2px;'
            'border-radius:22px 22px 0 0;">CERTIFICATE REVOKED</div>'
            '<div style="height:36px"></div>',
            1,
        )
    return Response(html_body, media_type="text/html", headers={
        "Cache-Control": "public, max-age=300" if revoked else "public, max-age=3600",
    })
<<<<<<< HEAD


# ───────────── Course share (marketplace OG preview) ────────────
@router.get("/courses/share/{course_id}", response_class=Response)
def course_share(course_id: int, request: Request, db: Session = Depends(get_db)):
    """Iter 48 — Public shareable link for a marketplace course.

    Social crawlers (WhatsApp/LinkedIn/Twitter) read the OpenGraph tags
    and unfurl the cover photo + star rating. Humans are redirected to
    the SPA course page via JS (crawlers don't execute it) with an HTML
    fallback card + link."""
    from sqlalchemy import func
    from models import CourseRating
    course = (
        db.query(Course)
        .join(Organization, Organization.id == Course.organization_id)
        .filter(Course.id == course_id)
        .filter(Course.status == CourseStatus.PUBLISHED)
        .filter(Organization.marketplace_opt_in == True)  # noqa: E712
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or not publicly listed")
    org = db.query(Organization).filter(Organization.id == course.organization_id).first()
    avg, n = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)) \
        .filter(CourseRating.course_id == course.id).one()

    base = _base(request)
    catalog_url = f"{base}/catalog/{course.id}"
    share_url = f"{base}/api/seo/courses/share/{course.id}"

    desc_bits = []
    if avg and n:
        plural = "s" if n != 1 else ""
        desc_bits.append(f"★ {round(float(avg), 1)} ({n} rating{plural})")
    desc_bits.append(f"{len(course.slides)} lessons")
    if course.duration_minutes:
        desc_bits.append(f"{course.duration_minutes} min")
    desc_bits.append("Free" if course.price_cents == 0
                     else f"{course.currency} {course.price_cents / 100:.2f}")
    if org:
        desc_bits.append(f"by {org.name}")
    description = " · ".join(desc_bits)
    if course.description:
        description = f"{course.description[:140].strip()} — {description}"

    image_url = ""
    cover = course.cover_image or (org.logo_url if org else None)
    if cover:
        image_url = cover if cover.startswith("http") else f"{base}{cover}"

    e_title = html.escape(course.title)
    e_desc = html.escape(description)
    e_img = html.escape(image_url)
    e_url = html.escape(share_url)
    e_catalog = html.escape(catalog_url)
    img_meta = (f'\n  <meta property="og:image" content="{e_img}" />'
                f'\n  <meta name="twitter:image" content="{e_img}" />') if image_url else ""
    stars = ""
    if avg and n:
        filled = "★" * round(float(avg))
        hollow = "☆" * (5 - round(float(avg)))
        plural = "s" if n != 1 else ""
        stars = (f'<p style="color:#f59e0b;font-size:20px;margin:0 0 4px;">'
                 f'{filled}{hollow} '
                 f'<span style="color:#64748b;font-size:14px;">{round(float(avg), 1)} · {n} rating{plural}</span></p>')

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{e_title}</title>
  <meta name="description" content="{e_desc}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{e_title}" />
  <meta property="og:description" content="{e_desc}" />
  <meta property="og:url" content="{e_url}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{e_title}" />
  <meta name="twitter:description" content="{e_desc}" />{img_meta}
  <script>window.location.replace("{e_catalog}");</script>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: linear-gradient(135deg, #eef2ff 0%, #ede9fe 100%);
      min-height: 100vh; margin: 0; display: flex;
      align-items: center; justify-content: center; padding: 24px; }}
    .card {{ background: white; border-radius: 24px; overflow: hidden;
      box-shadow: 0 20px 40px rgba(0,0,0,0.08); max-width: 560px; text-align: center; }}
    .card .inner {{ padding: 32px 40px 40px; }}
    .card img.cover {{ width: 100%; height: 240px; object-fit: cover; display: block; }}
    .card h1 {{ font-size: 26px; margin: 0 0 8px; color: #1e293b; }}
    .card p.meta {{ font-size: 14px; color: #64748b; margin: 0 0 24px; }}
    .card a {{ display: inline-block; background: #4f46e5; color: white;
      padding: 12px 24px; border-radius: 12px; text-decoration: none;
      font-weight: 600; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="card">
    {f'<img class="cover" src="{e_img}" alt="" />' if image_url else ''}
    <div class="inner">
      {stars}
      <h1>{e_title}</h1>
      <p class="meta">{e_desc}</p>
      <a href="{e_catalog}">View course</a>
    </div>
  </div>
</body>
</html>"""
    return Response(body, media_type="text/html",
                    headers={"Cache-Control": "public, max-age=3600"})
=======
>>>>>>> origin/main
