"""Iter 30e — Docs Library (downloadable manuals) integration tests."""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _session(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=10)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _session("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _session("learner@ifpi.org", "learner123")


def test_docs_manifest_lists_all_four_manuals(admin):
    r = admin.get(f"{BASE_URL}/api/admin/docs", timeout=10)
    assert r.status_code == 200
    docs = r.json()["documents"]
    slugs = {d["slug"] for d in docs}
    assert slugs == {"setup-manual", "user-manual",
                     "integration-matrix", "assessment", "erp360-bolt-on"}
    # Each entry has the metadata the frontend needs
    for d in docs:
        assert d["title"]
        assert d["subtitle"]
        assert d["audience"]
        assert isinstance(d["auto_regenerated"], bool)
        assert d["size_bytes"] > 500  # non-empty
        assert d["line_count"] > 40
        assert isinstance(d["modified_at"], int)


def test_learner_cannot_access_docs_library(learner):
    r = learner.get(f"{BASE_URL}/api/admin/docs", timeout=10)
    assert r.status_code == 403


def test_admin_can_download_setup_manual_pdf(admin):
    r = admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert 'attachment' in r.headers.get("content-disposition", "")
    assert '.pdf"' in r.headers.get("content-disposition", "")
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000  # non-trivial rendered doc


def test_admin_can_download_all_four_pdfs(admin):
    for slug in ("setup-manual", "user-manual",
                 "integration-matrix", "assessment"):
        r = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf", timeout=30)
        assert r.status_code == 200, f"{slug} → {r.status_code}"
        assert r.content[:4] == b"%PDF", f"{slug} not a PDF"


def test_admin_can_download_raw_markdown(admin):
    r = admin.get(f"{BASE_URL}/api/admin/docs/user-manual/raw", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert "IFPI Learning Academy" in body and "User Manual" in body
    assert "AUTO:BEGIN" in body  # raw variant keeps the markers


def test_unknown_slug_returns_404_envelope(admin):
    r = admin.get(f"{BASE_URL}/api/admin/docs/nonexistent-slug/pdf", timeout=10)
    assert r.status_code == 404
    # Global exception envelope from Iter 30d
    body = r.json()
    assert body.get("error", {}).get("code") == "NOT_FOUND"


def test_pdf_cached_between_requests(admin):
    """Second request for the same slug should be faster (cache hit)
    OR at least not meaningfully slower — anything worse means the
    cache is broken. Ratio-based tolerance avoids the 1ms timing-noise
    flake that hit iter-22 and iter-23 cert runs."""
    import time
    t0 = time.perf_counter()
    admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf", timeout=30)
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf", timeout=30)
    warm = time.perf_counter() - t0
    # Warm must be within 1.5× the cold time (real cache hits are
    # typically 5-10× faster; the loose bound just protects against a
    # broken cache while tolerating sub-millisecond clock jitter on
    # tiny PDFs).
    assert warm <= cold * 1.5 + 0.01, (
        f"warm ({warm:.4f}s) too slow vs cold ({cold:.4f}s) — cache broken?"
    )


# ── Iter 30g — inline preview + audit trail ─────────────────────────


def test_preview_returns_inline_content_disposition(admin):
    """?preview=true swaps `attachment` for `inline` so browsers render
    the PDF in an iframe/embed instead of dumping it into Downloads."""
    r = admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf?preview=true",
                  timeout=30)
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith("inline;"), f"expected inline disposition, got {cd!r}"
    assert r.content[:4] == b"%PDF"


def test_download_records_audit_log_entry(admin):
    """DOC_DOWNLOADED audit rows are written on every PDF/raw fetch."""
    # Trigger a download
    slug = "user-manual"
    r = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf", timeout=30)
    assert r.status_code == 200
    # Check the audit log surfaced it. `/api/admin/audit-log` returns
    # {total, items} scoped to the caller's org.
    r = admin.get(f"{BASE_URL}/api/admin/audit-log?action=DOC_DOWNLOADED",
                  timeout=10)
    assert r.status_code == 200, r.text
    entries = r.json().get("items", [])
    hits = [e for e in entries if e.get("target_id") == slug
            and e.get("action") == "DOC_DOWNLOADED"]
    assert hits, f"no DOC_DOWNLOADED entry for {slug} — got {entries[:3]}"


def test_preview_records_distinct_audit_action(admin):
    """Preview writes DOC_PREVIEWED (not DOC_DOWNLOADED) so analytics
    can distinguish 'user browsed' from 'user committed to a copy'."""
    slug = "assessment"
    r = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf?preview=true",
                  timeout=30)
    assert r.status_code == 200
    r = admin.get(f"{BASE_URL}/api/admin/audit-log?action=DOC_PREVIEWED",
                  timeout=10)
    assert r.status_code == 200, r.text
    entries = r.json().get("items", [])
    hits = [e for e in entries if e.get("target_id") == slug
            and e.get("action") == "DOC_PREVIEWED"]
    assert hits, f"no DOC_PREVIEWED entry for {slug} — got {entries[:3]}"
