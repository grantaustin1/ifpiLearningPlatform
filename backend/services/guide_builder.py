"""Render the user-guide markdown sources to branded PDFs.

Sources:  /app/docs/guides/{ADMIN,STUDENT}_USER_GUIDE.md
Outputs:  /app/docs/guides/IFPI_{Admin,Student}_User_Guide.pdf

`ensure_fresh(pdf_name)` rebuilds a PDF when its markdown source is newer
(or the PDF is missing) — called by the public download endpoint so the
served guides never go stale after a docs edit.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GUIDES_DIR = Path("/app/docs/guides")

# pdf filename -> (markdown source, subtitle)
GUIDES: dict[str, tuple[str, str]] = {
    "IFPI_Admin_User_Guide.pdf": ("ADMIN_USER_GUIDE.md", "Administrator User Guide"),
    "IFPI_Student_User_Guide.pdf": ("STUDENT_USER_GUIDE.md", "Student User Guide"),
}

CSS = """
@page {
    size: A4;
    margin: 2.2cm 1.9cm 2.4cm 1.9cm;
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        left: 54pt; width: 487pt; top: 790pt; height: 24pt;
    }
}
body { font-family: Helvetica; font-size: 10.5pt; color: #1e293b; line-height: 1.5; }
h1 { font-size: 21pt; color: #4f46e5; margin-bottom: 4pt; }
h2 { font-size: 14pt; color: #4f46e5; margin-top: 18pt; margin-bottom: 6pt;
     border-bottom: 1pt solid #c7d2fe; padding-bottom: 3pt; }
h3 { font-size: 11.5pt; color: #312e81; margin-top: 12pt; margin-bottom: 4pt; }
p { margin: 5pt 0; }
ul, ol { margin: 4pt 0 8pt 0; }
li { margin: 2pt 0; }
strong { color: #0f172a; }
code { font-family: Courier; font-size: 9.5pt; color: #4f46e5; }
blockquote { color: #475569; border-left: 3pt solid #a5b4fc;
             padding-left: 10pt; margin-left: 4pt; font-size: 10pt; }
table { width: 100%; border-collapse: collapse; margin: 8pt 0; font-size: 9.5pt; }
th { background-color: #4f46e5; color: #ffffff; padding: 5pt 7pt; text-align: left; }
td { border-bottom: 0.7pt solid #e2e8f0; padding: 5pt 7pt; }
hr { border: 0.5pt solid #e2e8f0; margin: 12pt 0; }
.cover-band { background-color: #4f46e5; color: #ffffff; padding: 16pt 18pt; margin-bottom: 16pt; }
.cover-band h1 { color: #ffffff; margin: 0; border: none; }
.cover-sub { color: #e0e7ff; font-size: 11pt; margin-top: 4pt; }
#footer_content { color: #94a3b8; font-size: 8.5pt; text-align: center; }
"""


def build(pdf_name: str) -> Path:
    """Render one guide. Raises on unknown name or build failure."""
    import markdown
    from xhtml2pdf import pisa

    md_file, subtitle = GUIDES[pdf_name]
    md_path = GUIDES_DIR / md_file
    md_text = md_path.read_text(encoding="utf-8")
    updated = datetime.fromtimestamp(md_path.stat().st_mtime).strftime("%-d %B %Y")
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]  # cover band replaces the markdown H1
    body_html = markdown.markdown("\n".join(lines), extensions=["tables", "sane_lists"])
    html = f"""<html><head><style>{CSS}</style></head><body>
    <div class="cover-band">
      <h1>IFPI Learning Platform</h1>
      <div class="cover-sub">{subtitle} &nbsp;&middot;&nbsp; Complete first-time walkthrough &nbsp;&middot;&nbsp; Updated {updated}</div>
    </div>
    {body_html}
    <div id="footer_content">IFPI Learning Platform — {subtitle} — updated {updated} — page <pdf:pagenumber> of <pdf:pagecount></div>
    </body></html>"""
    out = GUIDES_DIR / pdf_name
    buf = io.BytesIO()
    status = pisa.CreatePDF(io.StringIO(html), dest=buf, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"PDF build failed for {pdf_name}: {status.err} errors")
    out.write_bytes(buf.getvalue())
    return out


def ensure_fresh(pdf_name: str) -> Path:
    """Rebuild `pdf_name` iff missing or older than its markdown source.
    Returns the PDF path. If a rebuild fails but a previous PDF exists,
    the stale PDF is served rather than failing the download."""
    if pdf_name not in GUIDES:
        raise KeyError(pdf_name)
    pdf_path = GUIDES_DIR / pdf_name
    md_path = GUIDES_DIR / GUIDES[pdf_name][0]
    stale = (not pdf_path.is_file()
             or (md_path.is_file() and md_path.stat().st_mtime > pdf_path.stat().st_mtime))
    if stale:
        try:
            build(pdf_name)
            logger.info("guide_builder: rebuilt %s (source changed)", pdf_name)
        except Exception:
            logger.exception("guide_builder: rebuild of %s failed", pdf_name)
            if not pdf_path.is_file():
                raise
    return pdf_path
