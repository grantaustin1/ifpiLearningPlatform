"""Branded PDF certificate renderer using ReportLab.

Generates an A4-landscape certificate with:
- Organisation logo / wordmark
- Recipient name (large, centred)
- Course title + completion date
- Unique verification code + QR linking to the public /verify page
- Decorative gradient border + seal

The same template is used for course-completion certs and (later) exam-pass certs.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import httpx
import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _make_qr_image(url: str) -> io.BytesIO:
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _fetch_logo(logo_url: Optional[str]) -> Optional[io.BytesIO]:
    """Fetch a logo from URL or local path. Returns None on any failure
    so the cert still renders with a generated wordmark fallback."""
    if not logo_url:
        return None
    try:
        if logo_url.startswith(("http://", "https://")):
            with httpx.Client(timeout=5) as cli:
                r = cli.get(logo_url)
                r.raise_for_status()
            data = r.content
        else:
            with open(logo_url, "rb") as f:
                data = f.read()
        buf = io.BytesIO(data)
        buf.seek(0)
        return buf
    except Exception:
        return None


def render_certificate(
    *, recipient_name: str, course_title: str, certificate_code: str,
    issued_at: datetime, verify_url: str, organisation_name: str = "IFPI Learning",
    organisation_logo_url: Optional[str] = None,
    cert_type: str = "Course Completion",
    score: Optional[float] = None,
) -> bytes:
    """Returns the PDF as raw bytes — caller streams to client."""
    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # ── Background gradient (two stacked rectangles) ────────────────
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    # Decorative top band
    c.setFillColor(colors.HexColor("#6366f1"))
    c.rect(0, page_h - 25 * mm, page_w, 25 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#8b5cf6"))
    c.rect(0, 0, page_w, 12 * mm, fill=1, stroke=0)

    # ── Inner card ─────────────────────────────────────────────────
    inset = 18 * mm
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.setLineWidth(1)
    c.roundRect(inset, inset, page_w - 2 * inset, page_h - 2 * inset - 6 * mm,
                radius=8, fill=1, stroke=1)

    # ── Organisation logo OR wordmark (top centred) ────────────────
    logo_buf = _fetch_logo(organisation_logo_url)
    if logo_buf is not None:
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(logo_buf)
            iw, ih = img.getSize()
            target_h = 18 * mm
            target_w = target_h * (iw / ih) if ih else 40 * mm
            c.drawImage(img, (page_w - target_w) / 2, page_h - 48 * mm,
                        width=target_w, height=target_h, mask="auto")
        except Exception:
            logo_buf = None
    if logo_buf is None:
        c.setFillColor(colors.HexColor("#6366f1"))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_w / 2, page_h - 38 * mm, organisation_name.upper())

    # ── Big title ──────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(page_w / 2, page_h - 70 * mm, "Certificate")
    c.setFont("Helvetica", 18)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(page_w / 2, page_h - 82 * mm, "of " + cert_type)

    # ── "This is to certify that…" ─────────────────────────────────
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawCentredString(page_w / 2, page_h - 102 * mm, "This is to certify that")

    # ── Recipient name (very prominent) ────────────────────────────
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawCentredString(page_w / 2, page_h - 120 * mm, recipient_name or "Anonymous Learner")
    # underline-style accent
    c.setStrokeColor(colors.HexColor("#6366f1"))
    c.setLineWidth(2)
    text_w = c.stringWidth(recipient_name or "Anonymous Learner", "Helvetica-Bold", 32)
    c.line((page_w - text_w) / 2 - 10, page_h - 125 * mm,
           (page_w + text_w) / 2 + 10, page_h - 125 * mm)

    # ── "has successfully completed…" ──────────────────────────────
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(page_w / 2, page_h - 140 * mm,
                        "has successfully completed the course")
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawCentredString(page_w / 2, page_h - 152 * mm, course_title)

    if score is not None:
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#10b981"))
        c.drawCentredString(page_w / 2, page_h - 162 * mm,
                            f"with a score of {int(score)}%")

    # ── Bottom row: date (left) · seal (centre) · QR + code (right) ─
    bottom_y = inset + 18 * mm
    # Date
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(inset + 12 * mm, bottom_y + 10, "Date issued")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawString(inset + 12 * mm, bottom_y - 6,
                 issued_at.strftime("%d %B %Y"))

    # Seal in centre
    seal_x, seal_y = page_w / 2, bottom_y + 4
    c.setStrokeColor(colors.HexColor("#6366f1"))
    c.setLineWidth(1.5)
    c.circle(seal_x, seal_y, 14 * mm, fill=0, stroke=1)
    c.circle(seal_x, seal_y, 10 * mm, fill=0, stroke=1)
    c.setFillColor(colors.HexColor("#6366f1"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(seal_x, seal_y + 2, "VERIFIED")
    c.setFont("Helvetica", 7)
    c.drawCentredString(seal_x, seal_y - 6, "IFPI Learning")

    # QR + code on right
    qr_buf = _make_qr_image(verify_url)
    from reportlab.lib.utils import ImageReader
    qr_img = ImageReader(qr_buf)
    qr_size = 24 * mm
    qr_x = page_w - inset - 12 * mm - qr_size
    c.drawImage(qr_img, qr_x, bottom_y - 6, width=qr_size, height=qr_size, mask='auto')

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawRightString(page_w - inset - 12 * mm, bottom_y + qr_size, "Scan to verify")
    c.setFont("Courier", 8)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawRightString(page_w - inset - 12 * mm, bottom_y - 12, certificate_code)

    c.showPage()
    c.save()
    buf.seek(0)
    pdf_bytes = buf.read()
    buf.close()
    return pdf_bytes
