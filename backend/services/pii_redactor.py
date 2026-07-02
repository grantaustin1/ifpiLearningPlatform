"""PII redaction for AI prompts (Iter 22 — decision (b) — locked in Feb 2026).

Rule set (locked with product owner):
 - Default behaviour: `redact()` runs on every prompt AND every retrieved
   chunk before it goes to a third-party LLM. Emails, obvious names,
   phone numbers, national IDs, and long numeric strings get replaced
   with placeholders (`<learner_1>`, `<email_2>`, etc.).
 - The response received back from the LLM can be `unredact()`ed for
   the staff viewer using the mapping returned by `redact()`.
 - Callers must record `AuditLog(action="AI_PII_REDACT_DISABLED", ...)`
   whenever they choose to skip redaction — enforced at the router layer.

The regexes here are deliberately conservative (better to over-redact than
leak). If you need to widen them (e.g. add South African ID numbers),
add a new pattern to `_PATTERNS` — the counter/mapping mechanism handles
new categories automatically.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Tuple

logger = logging.getLogger("ifpi.ai.pii")

# Order matters — patterns tried in sequence, first match wins. Longer /
# more-specific patterns go first so they don't get eaten by shorter ones.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Email addresses
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    # International phone numbers (min 7 digits — E.164-ish)
    ("phone", re.compile(r"\+?\d[\d\s\-().]{6,}\d")),
    # South African ID / long numeric strings (>= 11 digits)
    ("national_id", re.compile(r"\b\d{11,}\b")),
    # First-Last name pairs — capitalised words separated by a space, both
    # 2+ chars. Kept last so we don't clobber capitalised acronyms in
    # emails/URLs (those regexes ran first).
    ("name", re.compile(r"\b[A-Z][a-z]{1,}\s+[A-Z][a-z]{1,}\b")),
]

# Common words that look like names but aren't (avoid `Learning Path`,
# `New York`, IFPI titles like `Foundation Course` etc.).
_NAME_ALLOWLIST = {
    "Learning Path", "Learning Paths", "New Course", "Foundation Course",
    "Practical Course", "Assessment Course", "Course Slide", "Course Slides",
    "Course Editor", "Admin Portal", "Learner Portal", "Time Zone",
    "Terms Of Service", "Privacy Policy", "Cookie Policy",
    "System Administrator", "Super Admin", "Content Imports",
    "Import Content", "Api Tokens", "Content Editor", "Video Overview",
    "Mind Map", "Deep Research", "Auto Quiz", "Auto Quizzes",
}


@dataclass
class RedactionResult:
    """Return value from `redact()`. Callers pass `mapping` to `unredact()`
    to restore original values in the LLM's response (for the staff UI)."""
    redacted_text: str
    mapping: Dict[str, str] = field(default_factory=dict)   # placeholder -> original
    counts: Dict[str, int] = field(default_factory=dict)    # category -> hits

    @property
    def redaction_applied(self) -> bool:
        return bool(self.mapping)


def redact(text: str) -> RedactionResult:
    """Replace PII in `text` with numbered placeholders. Returns the sanitised
    text + a mapping that lets you restore the originals later."""
    if not text:
        return RedactionResult(redacted_text=text or "", mapping={}, counts={})

    mapping: Dict[str, str] = {}
    reverse: Dict[str, str] = {}       # original → placeholder (for de-dup)
    counts: Dict[str, int] = {}

    result = text
    for category, pattern in _PATTERNS:
        def _sub(match: re.Match) -> str:
            original = match.group(0)
            # Skip names on the allowlist
            if category == "name" and original in _NAME_ALLOWLIST:
                return original
            # De-dup: same original value reuses the same placeholder
            if original in reverse:
                return reverse[original]
            n = counts.get(category, 0) + 1
            counts[category] = n
            placeholder = f"<{category}_{n}>"
            mapping[placeholder] = original
            reverse[original] = placeholder
            return placeholder

        result = pattern.sub(_sub, result)

    return RedactionResult(redacted_text=result, mapping=mapping, counts=counts)


def unredact(text: str, mapping: Dict[str, str]) -> str:
    """Restore original values in a redacted string. Use to un-redact an
    LLM response for the staff viewer while keeping the underlying prompt
    /response pair in the audit log with placeholders intact."""
    if not mapping or not text:
        return text or ""
    out = text
    # Sort by length desc so `<learner_10>` isn't clobbered by `<learner_1>`.
    for placeholder in sorted(mapping.keys(), key=len, reverse=True):
        out = out.replace(placeholder, mapping[placeholder])
    return out


def redact_many(*chunks: str) -> Tuple[list[str], Dict[str, str], Dict[str, int]]:
    """Redact several strings while sharing one placeholder counter — so
    `learner@ifpi.org` in chunk A and chunk B both map to `<email_1>`."""
    mapping: Dict[str, str] = {}
    reverse: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    out: list[str] = []
    for text in chunks:
        result = text or ""
        for category, pattern in _PATTERNS:
            def _sub(match: re.Match) -> str:
                original = match.group(0)
                if category == "name" and original in _NAME_ALLOWLIST:
                    return original
                if original in reverse:
                    return reverse[original]
                n = counts.get(category, 0) + 1
                counts[category] = n
                placeholder = f"<{category}_{n}>"
                mapping[placeholder] = original
                reverse[original] = placeholder
                return placeholder
            result = pattern.sub(_sub, result)
        out.append(result)
    return out, mapping, counts
