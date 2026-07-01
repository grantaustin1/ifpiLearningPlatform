"""HTML sanitizer for course slide content.

Wired into:
  - POST/PUT slide endpoints (defends against XSS from imported docx)
  - The bulk_import.py extractor (cleans docx HTML before storage)

Falls back to a tags-stripped string if bleach is unavailable so a missing
dep never blocks content from saving entirely — it just degrades gracefully.
"""
from __future__ import annotations

import logging
from typing import Optional

try:
    import bleach as _bleach
    _BLEACH = True
except ImportError:  # pragma: no cover — dependency present in prod
    _BLEACH = False

logger = logging.getLogger("ifpi.sanitizer")

ALLOWED_TAGS = frozenset([
    "p", "br", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "del", "ins",
    "ul", "ol", "li", "dl", "dt", "dd",
    "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
    "blockquote", "q", "cite", "code", "pre", "samp", "kbd",
    "mark", "small", "sub", "sup",
    "hr", "details", "summary",
    "iframe", "video", "audio", "source",
])

ALLOWED_ATTRS = {
    "*": ["class", "id", "title", "dir", "lang"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "iframe": ["src", "width", "height", "allow", "allowfullscreen", "sandbox"],
    "video": ["src", "width", "height", "controls", "poster", "preload"],
    "audio": ["src", "controls", "preload"],
    "source": ["src", "type"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]


def sanitize_course_html(raw: Optional[str]) -> str:
    """Sanitize HTML for storage in `CourseSlide.content`.

    - Strips disallowed tags (script, on*= handlers, javascript: URLs, etc.)
    - Keeps formatting, lists, tables, embedded media tags.
    - Returns "" for None / empty input.
    """
    if not raw:
        return ""
    if not _BLEACH:
        logger.warning("bleach not installed — returning escaped fallback")
        # Last-resort: strip ALL tags so nothing dangerous lands in the DB.
        import re
        return re.sub(r"<[^<>]+>", "", raw)
    return _bleach.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


def sanitize_plain_text(raw: Optional[str]) -> str:
    """For one-line fields where no HTML should ever appear (titles, etc.)."""
    if not raw:
        return ""
    if not _BLEACH:
        import re
        return re.sub(r"<[^<>]+>", "", raw).strip()
    return _bleach.clean(raw, tags=[], attributes={}, strip=True).strip()
