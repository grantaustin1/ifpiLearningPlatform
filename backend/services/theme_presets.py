"""Per-academy theme presets.

Curated combinations of primary color + cert accent + signature text style +
footer copy that an admin can apply in one click to make a brand-new academy
feel distinct from the default IFPI blue. Each preset is just a JSON object
that maps onto the existing `Organization` branding columns — no schema change
beyond the nullable `theme_preset` slug column added in migration c1f29b3e9d04.

When the admin applies a preset, the API copies the preset values onto the
Organization row and persists the preset's slug in `organization.theme_preset`
so the UI can show which preset is currently active. Future edits override
the preset (we don't lock the fields).

Pure data — no business logic. The list lives here so non-engineers can add
presets via a single edit + restart.
"""
from __future__ import annotations

from typing import Optional, TypedDict


class ThemePreset(TypedDict):
    slug: str
    name: str
    description: str
    primary_color: str
    cert_accent_color: str
    cert_signature_text_suggestion: str
    cert_footer_text_suggestion: str
    cover_color: str  # default tailwind cover for new courses


PRESETS: list[ThemePreset] = [
    {
        "slug": "ifpi_classic",
        "name": "IFPI Classic",
        "description": "The default indigo IFPI palette — clean, neutral, conference-floor friendly.",
        "primary_color": "#6366f1",
        "cert_accent_color": "#6366f1",
        "cert_signature_text_suggestion": "Frances Moore, CEO",
        "cert_footer_text_suggestion": "International Federation of the Phonographic Industry · ifpi.org",
        "cover_color": "bg-indigo-500",
    },
    {
        "slug": "conservatoire",
        "name": "Conservatoire",
        "description": "Deep burgundy + gold — for classical conservatoires and traditional music schools.",
        "primary_color": "#7f1d1d",
        "cert_accent_color": "#b45309",
        "cert_signature_text_suggestion": "Director of Studies",
        "cert_footer_text_suggestion": "Awarded under the academy's Royal Charter",
        "cover_color": "bg-red-900",
    },
    {
        "slug": "music_school",
        "name": "Modern Music School",
        "description": "Vibrant teal + magenta — for contemporary, electronic, and producer-focused academies.",
        "primary_color": "#0d9488",
        "cert_accent_color": "#db2777",
        "cert_signature_text_suggestion": "Head of Curriculum",
        "cert_footer_text_suggestion": "This certificate verifies completion of an approved music industry training programme.",
        "cover_color": "bg-teal-600",
    },
    {
        "slug": "industry_body",
        "name": "Industry Body",
        "description": "Slate + emerald — for trade associations, performing rights orgs, and member federations.",
        "primary_color": "#1e293b",
        "cert_accent_color": "#059669",
        "cert_signature_text_suggestion": "Chief Executive",
        "cert_footer_text_suggestion": "Issued on behalf of the membership.",
        "cover_color": "bg-slate-800",
    },
    {
        "slug": "label_academy",
        "name": "Label Academy",
        "description": "Monochrome black + neon yellow — for record-label-run training programs.",
        "primary_color": "#0a0a0a",
        "cert_accent_color": "#facc15",
        "cert_signature_text_suggestion": "Head of A&R Education",
        "cert_footer_text_suggestion": "A label-led training initiative.",
        "cover_color": "bg-neutral-900",
    },
]


def get_preset(slug: str) -> Optional[ThemePreset]:
    return next((p for p in PRESETS if p["slug"] == slug), None)
