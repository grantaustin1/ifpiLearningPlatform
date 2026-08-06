"""Tests for anonymous /api/public/guides/* PDF endpoints (Iter fix)."""
import os
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass  # CI — conftest auto-skips the suite when no backend is reachable

# unique per-test IP so we don't share the anonymous rate-limit bucket
def _hdr():
    return {"X-Test-Client-Ip": f"10.9.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"}


def test_admin_guide_download():
    r = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Admin_User_Guide.pdf", headers=_hdr(), timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content.startswith(b"%PDF"), "PDF magic bytes missing"
    assert len(r.content) > 5000
    cd = r.headers.get("content-disposition", "")
    assert "IFPI_Admin_User_Guide.pdf" in cd


def test_student_guide_download():
    r = requests.get(f"{BASE_URL}/api/public/guides/IFPI_Student_User_Guide.pdf", headers=_hdr(), timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 5000
    cd = r.headers.get("content-disposition", "")
    assert "IFPI_Student_User_Guide.pdf" in cd


def test_unknown_guide_returns_404():
    r = requests.get(f"{BASE_URL}/api/public/guides/notafile.pdf", headers=_hdr(), timeout=30)
    assert r.status_code == 404
    # must be JSON error, not SPA HTML
    ctype = r.headers.get("content-type", "")
    assert "json" in ctype, f"Expected JSON 404, got {ctype}: {r.text[:200]}"


def test_path_traversal_returns_404_no_leak():
    # URL-encoded traversal attempts
    for attempt in [
        "..%2F..%2Fbackend%2F.env",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "IFPI_Admin_User_Guide.pdf%00.txt",
    ]:
        r = requests.get(f"{BASE_URL}/api/public/guides/{attempt}", headers=_hdr(), timeout=30)
        assert r.status_code in (404, 400), f"{attempt} -> {r.status_code}"
        assert b"MONGO_URL" not in r.content
        assert b"root:" not in r.content
        assert not r.content.startswith(b"%PDF")


def test_certificate_verify_regression():
    # Regression: sibling anonymous endpoint must not 500 after guides route added
    r = requests.get(f"{BASE_URL}/api/public/certificates/verify/NONEXISTENTCODE123", headers=_hdr(), timeout=30)
    assert r.status_code in (200, 404), f"Unexpected {r.status_code}: {r.text[:200]}"
    assert "json" in r.headers.get("content-type", "")
