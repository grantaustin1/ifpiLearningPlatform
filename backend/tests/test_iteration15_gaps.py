"""Iteration 15 (gap-closure) — pinned deps + seed_templates.

Covers the checklist in the review request:
- Deps: bleach, python-docx, pandas, openpyxl, markdown import and match pins
- Sanitizer strips <script> (proves bleach is wired, not the no-op fallback)
- seed_templates.py: creates 3 templates, idempotent, correct slide counts,
  fails cleanly on unknown --org-id
- Course details (status/category/slide-count) visible via GET /api/courses/{id}
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"

BACKEND_DIR = "/app/backend"
ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}

# Expected pins (mirrors /app/backend/requirements.txt)
EXPECTED_VERSIONS = {
    "bleach": "6.4.0",
    "docx": "1.2.0",          # python-docx exposes package name `docx`
    "pandas": "3.0.3",
    "openpyxl": "3.1.5",
    "markdown": "3.10.2",
}


# ── Gap 1: dependency pinning ────────────────────────────────────────
class TestPinnedDeps:
    def test_all_five_modules_importable_with_correct_versions(self):
        for mod_name, expected in EXPECTED_VERSIONS.items():
            m = importlib.import_module(mod_name)
            ver = getattr(m, "__version__", None)
            if mod_name == "docx":
                # python-docx keeps version in docx.__version__ in >=1.0
                assert ver is not None, "python-docx must expose __version__"
                assert ver == expected, f"docx expected {expected} got {ver}"
            else:
                assert ver == expected, f"{mod_name} expected {expected} got {ver}"

    def test_requirements_txt_pins_all_five(self):
        with open(f"{BACKEND_DIR}/requirements.txt", "r", encoding="utf-8") as f:
            content = f.read()
        for token in ["bleach==6.4.0", "python-docx==1.2.0", "pandas==3.0.3",
                      "openpyxl==3.1.5", "markdown==3.10.2"]:
            assert token in content, f"{token} missing from requirements.txt"

    def test_bulk_import_module_loads(self):
        """Guards against ImportError during app cold-start."""
        if BACKEND_DIR not in sys.path:
            sys.path.insert(0, BACKEND_DIR)
        mod = importlib.import_module("scripts.bulk_import")
        assert hasattr(mod, "run_import_for_job")


class TestSanitizer:
    def test_script_tag_stripped(self):
        if BACKEND_DIR not in sys.path:
            sys.path.insert(0, BACKEND_DIR)
        from core import sanitizer
        # bleach should be wired (not the no-op fallback)
        assert sanitizer._BLEACH is True
        out = sanitizer.sanitize_course_html(
            "<script>alert(1)</script><p>ok</p>"
        )
        # bleach strips the <script> tag (text kept, but no executable HTML)
        assert "<script" not in out.lower()
        assert "</script>" not in out.lower()
        assert "<p>ok</p>" in out

    def test_plain_text_strips_all_tags(self):
        if BACKEND_DIR not in sys.path:
            sys.path.insert(0, BACKEND_DIR)
        from core import sanitizer
        assert sanitizer.sanitize_plain_text("<b>hi</b>") == "hi"


# ── Gap 2: seed_templates.py ─────────────────────────────────────────
def _run_seed(org_id: int):
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_templates", "--org-id", str(org_id)],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=60,
    )


def _admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


TEMPLATE_TITLES = ["[TEMPLATE] Foundation", "[TEMPLATE] Practical", "[TEMPLATE] Assessment"]
EXPECTED_SLIDES = {
    "[TEMPLATE] Foundation": 5,
    "[TEMPLATE] Practical": 5,
    "[TEMPLATE] Assessment": 4,
}


class TestSeedTemplates:
    def test_seed_org_1_idempotent(self):
        """First run may create-or-skip, second run MUST be 0 created / 3 skipped."""
        # Prime the row (either creates 3 or skips 3 if already present)
        r1 = _run_seed(1)
        assert r1.returncode == 0, r1.stderr + r1.stdout
        # Second run — guaranteed idempotent
        r2 = _run_seed(1)
        assert r2.returncode == 0, r2.stderr + r2.stdout
        assert "Created: 0" in r2.stdout, r2.stdout
        assert "Skipped: 3" in r2.stdout, r2.stdout
        for title in TEMPLATE_TITLES:
            assert title in r2.stdout, f"missing {title} in output"

    def test_templates_visible_via_api_with_correct_shape(self):
        # Ensure exists
        _run_seed(1)
        s = _admin_session()
        listing = s.get(f"{BASE_URL}/api/courses",
                        params={"category": "TEMPLATE"}, timeout=15)
        # Fall back to unfiltered list if category filter isn't wired
        if listing.status_code != 200:
            listing = s.get(f"{BASE_URL}/api/courses", timeout=15)
        assert listing.status_code == 200, listing.text
        payload = listing.json()
        items = payload.get("items") if isinstance(payload, dict) else payload
        assert isinstance(items, list)

        found = {t: None for t in TEMPLATE_TITLES}
        for c in items:
            if c.get("title") in found:
                found[c["title"]] = c
        missing = [t for t, v in found.items() if v is None]
        assert not missing, f"Templates missing from /api/courses: {missing}"

        for title, course in found.items():
            cid = course["id"]
            detail = s.get(f"{BASE_URL}/api/courses/{cid}", timeout=15).json()
            assert detail.get("category") == "TEMPLATE", detail
            # status may be enum-string 'DRAFT' or 'draft'
            assert str(detail.get("status", "")).upper() == "DRAFT", detail
            slides = detail.get("slides") or detail.get("course_slides") or []
            assert len(slides) == EXPECTED_SLIDES[title], (
                f"{title}: expected {EXPECTED_SLIDES[title]} slides, got {len(slides)}"
            )

    def test_seed_unknown_org_exits_nonzero(self):
        r = _run_seed(999999)
        assert r.returncode != 0
        combined = (r.stderr + r.stdout).lower()
        assert "not found" in combined or "organization" in combined
