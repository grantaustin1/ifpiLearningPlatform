from __future__ import annotations

from fastapi import Depends

from auth.dependencies import CurrentUser, requires_roles

from auth.dependencies import CurrentUser, requires_roles

from . import richtext_router


@richtext_router.post("/sanitize")
def sanitize_html_payload(body: dict,
                          _current: CurrentUser = Depends(requires_roles(
                              "INSTRUCTOR", "ADMIN", "SUPER_ADMIN"))):
    """Server-side HTML sanitizer for the rich-text editor preview.
    Strips dangerous tags/attrs while preserving formatting + media tags.
    """
    from core.sanitizer import sanitize_course_html
    raw = body.get("html") or ""
    return {"sanitized": sanitize_course_html(raw), "input_length": len(raw)}
