"""Iter 41 — Help sidebar, guide auto-rebuild, marketplace cleanup."""
import os
import time
import subprocess
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL is required"

GUIDES_DIR = Path("/app/docs/guides")
STUDENT_PDF = GUIDES_DIR / "IFPI_Student_User_Guide.pdf"
STUDENT_MD = GUIDES_DIR / "STUDENT_USER_GUIDE.md"
ADMIN_PDF = GUIDES_DIR / "IFPI_Admin_User_Guide.pdf"


def _hdr(ip="10.41.0.1"):
    return {"X-Test-Client-Ip": ip}


# ── Guides download (anonymous) ───────────────────────────────────────
class TestGuidesDownload:
    def test_admin_guide_download(self):
        r = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Admin_User_Guide.pdf",
                         headers=_hdr("10.41.0.2"), timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_student_guide_download(self):
        r = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Student_User_Guide.pdf",
                         headers=_hdr("10.41.0.3"), timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# ── Guide auto-rebuild when markdown source changes ───────────────────
class TestGuideAutoRebuild:
    def test_touch_md_triggers_rebuild_and_second_get_is_idempotent(self):
        # Baseline: ensure both files exist
        assert STUDENT_MD.is_file(), "student MD must exist"
        # Prime the PDF (ensure exists)
        r0 = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Student_User_Guide.pdf",
                          headers=_hdr("10.41.0.4"), timeout=30)
        assert r0.status_code == 200
        assert STUDENT_PDF.is_file()

        pdf_mtime_before = STUDENT_PDF.stat().st_mtime

        # Touch markdown so its mtime is newer than the PDF
        time.sleep(1.1)  # ensure a filesystem-visible delta
        now = time.time()
        os.utime(STUDENT_MD, (now, now))
        md_mtime_after_touch = STUDENT_MD.stat().st_mtime
        assert md_mtime_after_touch > pdf_mtime_before

        # GET should trigger rebuild
        r1 = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Student_User_Guide.pdf",
                          headers=_hdr("10.41.0.5"), timeout=60)
        assert r1.status_code == 200
        assert r1.headers.get("content-type", "").startswith("application/pdf")
        assert r1.content[:4] == b"%PDF"

        pdf_mtime_after_first = STUDENT_PDF.stat().st_mtime
        assert pdf_mtime_after_first > pdf_mtime_before, (
            f"PDF was not rebuilt: before={pdf_mtime_before} after={pdf_mtime_after_first}"
        )
        # PDF should now be newer than the markdown (rebuild happened AFTER touch)
        assert pdf_mtime_after_first >= md_mtime_after_touch - 0.001

        # Second GET must NOT rebuild
        time.sleep(0.5)
        r2 = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Student_User_Guide.pdf",
                          headers=_hdr("10.41.0.6"), timeout=30)
        assert r2.status_code == 200
        pdf_mtime_after_second = STUDENT_PDF.stat().st_mtime
        assert pdf_mtime_after_second == pdf_mtime_after_first, (
            f"PDF was rebuilt unnecessarily on second GET "
            f"({pdf_mtime_after_first} -> {pdf_mtime_after_second})"
        )


# ── Marketplace catalog cleanup verification ──────────────────────────
class TestMarketplaceCleanup:
    @pytest.fixture(scope="class")
    def catalog_all(self):
        # Fetch pages until we have everything
        courses = []
        page = 1
        while True:
            r = requests.get(f"{BASE_URL}/api/catalog",
                             params={"page": page, "page_size": 100},
                             timeout=30)
            assert r.status_code == 200, r.text[:200]
            data = r.json()
            courses.extend(data.get("courses", []))
            total = data.get("total", 0)
            if len(courses) >= total or not data.get("courses"):
                break
            page += 1
            if page > 30:
                break
        return courses

    def test_catalog_contains_ifpi_fundamentals(self, catalog_all):
        titles = [c["title"] for c in catalog_all]
        assert any("IFPI Fundamentals" in t for t in titles), (
            f"IFPI Fundamentals missing from catalog. Sample titles: {titles[:15]}"
        )

    def test_catalog_no_debris_courses(self, catalog_all):
        bad_prefixes = ("Stripe Test", "Ent Inspect", "Entitlement Test",
                        "Paid E2E", "TEST_", "Stripe Frontend E2E")
        offenders = [c["title"] for c in catalog_all
                     if any(c["title"].startswith(p) for p in bad_prefixes)]
        assert not offenders, f"Debris courses still in catalog: {offenders}"

    def test_catalog_no_faker_orgs(self, catalog_all):
        # Nelson PLC style faker-company names
        faker_suffixes = (" PLC", " LLC", " Inc", " Ltd", " and Sons", " Group")
        # Only flag if org name looks fake AND is not an IFPI org
        offenders = []
        for c in catalog_all:
            org = (c.get("organization") or {}).get("name", "") or ""
            if "IFPI" in org or "ifpi" in org.lower():
                continue
            if any(org.endswith(s) for s in faker_suffixes):
                offenders.append(org)
        # Just report; some real orgs might have "Group" etc.
        # Hard check: no "Nelson PLC" specifically (documented in problem stmt)
        assert not any("Nelson PLC" in ((c.get("organization") or {}).get("name", "") or "")
                       for c in catalog_all), (
            "Nelson PLC (faker debris) still in catalog"
        )
        if offenders:
            print(f"WARNING: possible faker orgs in catalog: {set(offenders)}")


# ── Nightly cleanup: dry-run must include marketplace_optouts key ─────
class TestNightlyCleanupDryRun:
    def test_tick_dry_run_returns_marketplace_optouts_key(self):
        cmd = [
            "python", "-c",
            "import sys; sys.path.insert(0, '/app/backend'); "
            "from core.database import SessionLocal; "
            "from services.test_debris_cleanup import tick; "
            "db = SessionLocal(); "
            "stats = tick(db, dry_run=True); "
            "db.close(); "
            "print('STATS:', stats); "
            "assert 'marketplace_optouts' in stats, 'missing marketplace_optouts'; "
        ]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                cwd="/app/backend", timeout=60)
        assert result.returncode == 0, (
            f"dry-run failed: stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "marketplace_optouts" in result.stdout
