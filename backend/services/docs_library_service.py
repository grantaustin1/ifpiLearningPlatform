"""Docs Library service (Iter 30e).

Serves the four IFPI manuals (Setup, User, Integration Matrix,
Assessment) as **downloadable PDFs**, plus a manifest endpoint so the
Documents tab in Organization Settings can list them dynamically.

Design decisions
----------------
- Uses `markdown` (already in requirements) → HTML → `xhtml2pdf` for PDF
  rendering. xhtml2pdf is pure-Python and doesn't need cairo/pango like
  WeasyPrint — small footprint.
- PDFs are generated **on the fly** so the manuals stay in sync with the
  auto-generated AUTO-BLOCKs. Rendered PDFs are cached in `/tmp` for
  1 hour to smooth repeat downloads.
- Only exposes files that live in `/app/docs/` (defence-in-depth path
  traversal check).

Slugs are stable and lowercase; the frontend uses them as-is.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("ifpi.docs_library")

DOCS_ROOT = Path("/app/docs")
CACHE_DIR = Path("/tmp/ifpi_docs_cache")
CACHE_TTL_SECS = 3600  # 1 hour


# Catalog of exposed manuals — slug → filename + human title + audience.
# Order controls display in the UI.
CATALOG: Dict[str, dict] = {
    "setup-manual": {
        "file": "IFPI_SETUP_MANUAL.md",
        "title": "IFPI Setup Manual",
        "subtitle": "6-phase Idiots Guide for tenant onboarding",
        "audience": "Owner, Super Admin",
        "auto_regenerated": True,
    },
    "user-manual": {
        "file": "IFPI_USER_MANUAL.md",
        "title": "IFPI User Manual",
        "subtitle": "Complete feature reference for all roles",
        "audience": "All roles",
        "auto_regenerated": True,
    },
    "integration-matrix": {
        "file": "IFPI_INTEGRATION_MATRIX.md",
        "title": "IFPI ↔ ERP360 Integration Matrix",
        "subtitle": "Sibling-vs-standalone contract",
        "audience": "Platform Ops, Owner",
        "auto_regenerated": False,
    },
    "assessment": {
        "file": "IFPI_VS_ERP360_ASSESSMENT.md",
        "title": "IFPI vs ERP360 — Comparative Assessment",
        "subtitle": "Security, tests, scalability, roadmap",
        "audience": "Owner, Platform Ops",
        "auto_regenerated": False,
    },
}


def list_manifest() -> List[dict]:
    """Return an ordered list of documents with metadata. Includes file
    size (of the source .md) + last-modified timestamp so the UI can
    show freshness."""
    out: List[dict] = []
    for slug, meta in CATALOG.items():
        src = DOCS_ROOT / meta["file"]
        if not src.exists():
            continue
        stat = src.stat()
        out.append({
            "slug": slug,
            "title": meta["title"],
            "subtitle": meta["subtitle"],
            "audience": meta["audience"],
            "auto_regenerated": meta["auto_regenerated"],
            "source_file": meta["file"],
            "size_bytes": stat.st_size,
            "line_count": _line_count(src),
            "modified_at": int(stat.st_mtime),
        })
    return out


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def render_pdf(slug: str) -> Optional[Tuple[bytes, str]]:
    """Return (pdf_bytes, download_filename) or None if the slug is
    unknown / source file missing."""
    meta = CATALOG.get(slug)
    if not meta:
        return None
    src = DOCS_ROOT / meta["file"]
    if not src.exists():
        return None
    # Cache key includes mtime so edits invalidate automatically
    key_material = f"{slug}:{src.stat().st_mtime_ns}:{src.stat().st_size}"
    key = hashlib.sha256(key_material.encode()).hexdigest()[:16]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{slug}-{key}.pdf"
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < CACHE_TTL_SECS:
        pdf_bytes = cache_file.read_bytes()
    else:
        pdf_bytes = _md_to_pdf(src, title=meta["title"])
        # Best-effort cache write
        try:
            cache_file.write_bytes(pdf_bytes)
        except OSError as exc:  # noqa: BLE001
            logger.warning("could not write docs cache: %s", exc)
    filename = meta["file"].replace(".md", ".pdf")
    return pdf_bytes, filename


def _md_to_pdf(src: Path, title: str) -> bytes:
    """Markdown → styled HTML → PDF via xhtml2pdf."""
    import markdown
    from xhtml2pdf import pisa

    md_text = src.read_text(encoding="utf-8")

    # Strip AUTO-BLOCK comments so they don't clutter the PDF, keeping
    # only the generated content between them.
    md_text = _strip_auto_markers(md_text)

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "attr_list"],
    )

    css = """
        @page { size: A4; margin: 22mm 18mm 22mm 18mm;
                @frame footer { -pdf-frame-content: pageFooter;
                                bottom: 8mm; left: 18mm; right: 18mm; height: 8mm; } }
        body { font-family: Helvetica, Arial, sans-serif; color: #0f172a;
               font-size: 10pt; line-height: 1.45; }
        h1 { font-size: 22pt; color: #1e293b; border-bottom: 2px solid #cbd5e1;
             padding-bottom: 6px; margin-top: 14pt; }
        h2 { font-size: 15pt; color: #1e293b; margin-top: 14pt;
             border-bottom: 1px solid #e2e8f0; padding-bottom: 3px; }
        h3 { font-size: 12pt; color: #334155; margin-top: 10pt; }
        h4 { font-size: 11pt; color: #475569; }
        a { color: #4f46e5; text-decoration: none; }
        code { font-family: Menlo, Consolas, monospace; font-size: 9pt;
               background: #f1f5f9; padding: 0 3px; border-radius: 2px;
               color: #b91c1c; }
        pre { background: #0f172a; color: #f8fafc; padding: 8pt;
              font-size: 8.5pt; border-radius: 4pt; }
        pre code { background: transparent; color: inherit; }
        table { border-collapse: collapse; width: 100%; margin: 8pt 0;
                font-size: 9pt; }
        th, td { border: 1px solid #cbd5e1; padding: 4pt 6pt; text-align: left; }
        th { background: #e2e8f0; color: #0f172a; }
        blockquote { border-left: 3px solid #94a3b8; margin: 8pt 0;
                     padding: 4pt 10pt; color: #475569; }
        hr { border: none; border-top: 1px solid #cbd5e1; margin: 10pt 0; }
        img { max-width: 100%; margin: 8pt 0; border: 1px solid #e2e8f0;
              border-radius: 4pt; }
        .cover { text-align: center; padding-top: 60mm; }
        .cover h1 { font-size: 30pt; border: none; }
        .cover .meta { color: #64748b; font-size: 12pt; margin-top: 12pt; }
    """

    cover = f"""
    <div class="cover">
      <h1>{title}</h1>
      <p class="meta">IFPI Learning Academy · Documentation</p>
      <p class="meta">Generated {time.strftime('%B %d, %Y')}</p>
    </div>
    <div style="page-break-after: always;"></div>
    """

    footer = (
        '<div id="pageFooter" style="text-align:right;color:#94a3b8;'
        'font-size:8pt;border-top:1px solid #cbd5e1;padding-top:2mm;">'
        f'{title} · Page <pdf:pagenumber> of <pdf:pagecount>'
        '</div>'
    )

    full_html = (
        f"<html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{css}</style></head>"
        f"<body>{cover}{html_body}{footer}</body></html>"
    )

    buf = io.BytesIO()

    def _resolve_asset(uri: str, _rel: str) -> str:
        """xhtml2pdf link callback — resolves relative image paths in
        the markdown (e.g. `screenshots/03-owner-dashboard.png`) to real
        files inside /app/docs. Also allows absolute /app paths for
        Platform Ops flexibility."""
        if uri.startswith(("http://", "https://", "data:")):
            return uri
        if uri.startswith("/"):
            return uri if os.path.exists(uri) else uri
        candidate = (DOCS_ROOT / uri).resolve()
        # Path traversal guard — must remain under DOCS_ROOT
        try:
            candidate.relative_to(DOCS_ROOT)
        except ValueError:
            return uri
        return str(candidate) if candidate.exists() else uri

    result = pisa.CreatePDF(
        src=full_html, dest=buf, encoding="utf-8",
        link_callback=_resolve_asset,
    )
    if result.err:
        raise RuntimeError(f"xhtml2pdf reported {result.err} errors")
    return buf.getvalue()


def _strip_auto_markers(md: str) -> str:
    """Remove the `<!-- AUTO:BEGIN/END X -->` comments so the printed
    PDF doesn't show them. Keeps the content between."""
    import re
    return re.sub(r"<!-- AUTO:(BEGIN|END) \w+ -->\n?", "", md)
