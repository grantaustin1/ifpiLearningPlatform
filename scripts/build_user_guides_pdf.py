"""Render the admin + student user guides (markdown) to branded PDFs.

Run:  python /app/scripts/build_user_guides_pdf.py
Outputs to /app/frontend/public/guides/ so they're downloadable from the app URL.
"""
import io
from pathlib import Path

import markdown
from xhtml2pdf import pisa

GUIDES = [
    ("/app/docs/guides/ADMIN_USER_GUIDE.md", "IFPI_Admin_User_Guide.pdf",
     "Administrator User Guide"),
    ("/app/docs/guides/STUDENT_USER_GUIDE.md", "IFPI_Student_User_Guide.pdf",
     "Student User Guide"),
]
OUT_DIR = Path("/app/frontend/public/guides")

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


def build(md_path: str, pdf_name: str, subtitle: str) -> Path:
    md_text = Path(md_path).read_text(encoding="utf-8")
    # Drop the first markdown H1 — replaced by the styled cover band.
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body_html = markdown.markdown("\n".join(lines), extensions=["tables", "sane_lists"])
    html = f"""<html><head><style>{CSS}</style></head><body>
    <div class="cover-band">
      <h1>IFPI Learning Platform</h1>
      <div class="cover-sub">{subtitle} &nbsp;&middot;&nbsp; Version 2.0 &nbsp;&middot;&nbsp; July 2026 &nbsp;&middot;&nbsp; Complete first-time walkthrough</div>
    </div>
    {body_html}
    <div id="footer_content">IFPI Learning Platform — {subtitle} — page <pdf:pagenumber> of <pdf:pagecount></div>
    </body></html>"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / pdf_name
    buf = io.BytesIO()
    status = pisa.CreatePDF(io.StringIO(html), dest=buf, encoding="utf-8")
    if status.err:
        raise SystemExit(f"PDF build failed for {pdf_name}: {status.err} errors")
    out.write_bytes(buf.getvalue())
    return out


if __name__ == "__main__":
    for md, name, sub in GUIDES:
        p = build(md, name, sub)
        print(f"built {p} ({p.stat().st_size // 1024} KB)")
