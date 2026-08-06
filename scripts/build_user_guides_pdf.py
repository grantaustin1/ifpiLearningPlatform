"""Thin wrapper — real logic lives in backend/services/guide_builder.py.
The public download endpoint auto-rebuilds stale PDFs; run this only to
force a rebuild from the CLI.

Run:  python /app/scripts/build_user_guides_pdf.py
"""
import sys

sys.path.insert(0, "/app/backend")

from services.guide_builder import GUIDES, build

if __name__ == "__main__":
    for name in GUIDES:
        p = build(name)
        print(f"built {p} ({p.stat().st_size // 1024} KB)")
