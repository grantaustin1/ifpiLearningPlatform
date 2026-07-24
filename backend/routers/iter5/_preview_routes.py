from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Request, Response

from auth.dependencies import CurrentUser, requires_roles
from core.config import settings

from . import preview_router
from ._schemas import CertPreviewBody


@preview_router.post("")
def preview_cert(
    body: CertPreviewBody,
    request: Request,
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    """Render a SAMPLE certificate PDF using the supplied branding — no DB writes.
    Used by the Settings page Live Preview."""
    from services.pdf_certificate_service import render_certificate
    base = settings.public_base_url or str(request.base_url).rstrip("/")
    pdf = render_certificate(
        recipient_name="Jane Sample",
        course_title="Sample Course Title",
        certificate_code="PREVIEW-XXXXX",
        issued_at=datetime.now(timezone.utc),
        verify_url=f"{base}/verify/PREVIEW-XXXXX",
        organisation_name=body.organisation_name or "Sample Academy",
        organisation_logo_url=body.organisation_logo_url,
        accent_color=body.accent_color or "#6366f1",
        signature_text=body.signature_text,
        signature_image_url=body.signature_image_url,
        footer_text=body.footer_text,
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Cache-Control": "no-store"},
    )
