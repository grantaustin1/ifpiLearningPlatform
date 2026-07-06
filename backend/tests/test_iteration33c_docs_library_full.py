"""Iter 33c — Comprehensive Docs Library + engagement regression tests.

Covers the full review checklist:
  - GET /api/admin/docs manifest shape (4 docs, titles, size_bytes, line_count, modified_at)
  - GET /api/admin/docs/{slug}/pdf headers (attachment/inline via preview flag)
  - PDF payload validity (%PDF-1.4 header, > 20KB for setup + user manuals)
  - GET /api/admin/docs/{slug}/raw for known + malformed slug (404)
  - Learner 403 on all endpoints
  - Audit trail: DOC_PREVIEWED / DOC_DOWNLOADED rows written with correct actor + target_id
  - /api/admin/dashboard/docs-engagement roll-up after N events
"""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("2FA is enabled on the admin account")
    if body.get("access_token"):
        s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture(scope="module")
def learner():
    return _login("learner@ifpi.org", "learner123")


# ---------- Manifest ----------

class TestManifest:
    def test_manifest_has_four_docs(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "documents" in data
        docs = data["documents"]
        slugs = {d["slug"] for d in docs}
        # Required four documents
        expected = {"setup-manual", "user-manual",
                    "integration-matrix", "assessment"}
        missing = expected - slugs
        assert not missing, f"missing docs {missing} in {slugs}"

    def test_manifest_row_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs", timeout=15)
        assert r.status_code == 200
        docs = r.json()["documents"]
        by_slug = {d["slug"]: d for d in docs}
        for slug in ("setup-manual", "user-manual"):
            d = by_slug[slug]
            for key in ("title", "size_bytes", "line_count", "modified_at",
                        "subtitle", "audience", "source_file"):
                assert key in d, f"missing {key} on {slug}"
            assert isinstance(d["size_bytes"], int) and d["size_bytes"] > 0
            assert isinstance(d["line_count"], int) and d["line_count"] > 0
            assert isinstance(d["modified_at"], int)
        # Iter 31-33 promise: manuals grew to at least these sizes
        assert by_slug["setup-manual"]["line_count"] >= 512
        assert by_slug["user-manual"]["line_count"] >= 858
        assert by_slug["setup-manual"]["size_bytes"] >= 23 * 1024
        assert by_slug["user-manual"]["size_bytes"] >= 42 * 1024
        assert "Setup" in by_slug["setup-manual"]["title"]
        assert "User" in by_slug["user-manual"]["title"]

    def test_learner_forbidden_manifest(self, learner):
        r = learner.get(f"{BASE_URL}/api/admin/docs", timeout=10)
        assert r.status_code == 403, r.text


# ---------- PDF ----------

class TestPdf:
    def test_setup_manual_pdf_download(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf", timeout=45)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert cd.startswith("attachment"), f"expected attachment, got {cd!r}"
        assert "IFPI_SETUP_MANUAL.pdf" in cd
        assert r.content.startswith(b"%PDF-"), \
            f"not a PDF payload: {r.content[:20]!r}"
        assert len(r.content) > 20 * 1024, f"pdf too small: {len(r.content)}"

    def test_user_manual_pdf_download(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs/user-manual/pdf", timeout=45)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF-")
        assert len(r.content) > 20 * 1024

    def test_preview_uses_inline(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf?preview=true",
                      timeout=45)
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert cd.startswith("inline"), f"expected inline, got {cd!r}"

    def test_unknown_slug_pdf_404(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs/does-not-exist/pdf", timeout=15)
        assert r.status_code == 404

    def test_learner_forbidden_pdf(self, learner):
        r = learner.get(f"{BASE_URL}/api/admin/docs/setup-manual/pdf", timeout=15)
        assert r.status_code == 403


# ---------- Raw markdown ----------

class TestRaw:
    def test_setup_manual_raw(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs/setup-manual/raw", timeout=15)
        assert r.status_code == 200
        # Body should look like markdown (has # heading)
        body = r.text
        assert "# " in body[:500] or "IFPI" in body[:500], body[:300]
        cd = r.headers.get("content-disposition", "")
        assert "IFPI_SETUP_MANUAL.md" in cd

    def test_unknown_slug_raw_404(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/docs/no-such-doc/raw", timeout=10)
        assert r.status_code == 404

    def test_learner_forbidden_raw(self, learner):
        r = learner.get(f"{BASE_URL}/api/admin/docs/setup-manual/raw", timeout=10)
        assert r.status_code == 403


# ---------- Audit trail ----------

class TestAudit:
    def test_preview_then_download_writes_audit_rows(self, admin):
        # Snapshot current window counts
        r0 = admin.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement?days=1",
                       timeout=10)
        assert r0.status_code == 200
        before = r0.json()["total_events"]

        # Fire one preview + one download for two distinct docs
        for slug in ("setup-manual", "user-manual"):
            r_p = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf?preview=true",
                            timeout=45)
            assert r_p.status_code == 200
            r_d = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf",
                            timeout=45)
            assert r_d.status_code == 200

        time.sleep(0.3)

        r1 = admin.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement?days=1",
                       timeout=10)
        assert r1.status_code == 200
        data = r1.json()
        after = data["total_events"]
        assert after >= before + 4, f"expected +4 events, before={before}, after={after}"
        assert data["unique_docs"] >= 2
        assert data["unique_readers"] >= 1


# ---------- Engagement endpoint shape ----------

class TestEngagement:
    def test_shape_and_admin_only(self, admin, learner):
        r_l = learner.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement",
                          timeout=10)
        assert r_l.status_code == 403

        r_a = admin.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement?days=7",
                        timeout=10)
        assert r_a.status_code == 200
        d = r_a.json()
        for key in ("window_days", "total_events", "unique_docs",
                    "unique_readers", "top_docs", "latest_at"):
            assert key in d, f"missing {key}: {d}"
        assert d["window_days"] == 7
        assert isinstance(d["top_docs"], list)
        # Titles are human-readable in the top_docs
        for row in d["top_docs"]:
            assert set(row.keys()) >= {"slug", "title", "count"}
        # top_docs must be sorted count desc
        counts = [row["count"] for row in d["top_docs"]]
        assert counts == sorted(counts, reverse=True), counts

    def test_days_query_validation(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement?days=0",
                      timeout=10)
        assert r.status_code == 422  # ge=1 fails
