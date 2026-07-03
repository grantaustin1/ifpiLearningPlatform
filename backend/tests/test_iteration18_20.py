"""Iteration 18-20 regression suite.

Covers:
 - Iter 18: SCORM parser + upload + serve, xAPI receiver + list
 - Iter 19: Slide versioning (auto-snapshot on edit, list, restore), HTML sanitizer
 - Iter 20: server.py refactor — all routers still mounted (smoke OpenAPI)
 + Iter 17 improvement: ImportJob rollback
"""
from __future__ import annotations

import io
import os
import uuid
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    import pytest
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests", allow_module_level=True)

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(**ADMIN)


# ── Iter 20: server.py refactor — all routes mounted ──────────────────
def test_openapi_lists_all_expected_routes(admin):
    schema = requests.get(f"{BASE_URL}/api/openapi.json", timeout=15).json()
    paths = set(schema["paths"].keys())
    # Spot-check one route per iteration / domain
    must_have = [
        "/api/auth/login", "/api/courses", "/api/exams",
        "/api/learning-paths", "/api/admin/invitations",
        "/api/admin/outbox", "/api/admin/webhooks",
        "/api/admin/imports", "/api/admin/imports/upload-zip",
        "/api/admin/storage/info",
        "/api/admin/scorm/upload", "/api/xapi/statements",
        "/api/rich-text/sanitize",
    ]
    missing = [p for p in must_have if p not in paths]
    assert not missing, f"refactor lost routes: {missing}"


# ── Iter 18: SCORM ────────────────────────────────────────────────────
def _build_scorm_zip(title: str = "Iter18 Pytest SCORM") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "imsmanifest.xml",
            f'<?xml version="1.0"?>'
            f'<manifest identifier="iter18" version="1" '
            f'xmlns="http://www.imsglobal.org/xsd/imscp_v1p1">'
            f'<metadata><schemaversion>1.2</schemaversion></metadata>'
            f'<organizations default="ORG-1">'
            f'<organization identifier="ORG-1"><title>{title}</title>'
            f'<item identifier="I1" identifierref="R1"><title>Welcome</title></item>'
            f'</organization></organizations>'
            f'<resources><resource identifier="R1" type="webcontent" href="index.html">'
            f'<file href="index.html"/></resource></resources>'
            f'</manifest>',
        )
        zf.writestr("index.html",
                    "<!doctype html><html><body><h1>SCORM 1.2 Test</h1></body></html>")
    return buf.getvalue()


def test_scorm_upload_parses_and_serves(admin):
    title = f"Iter18 SCORM {uuid.uuid4().hex[:6]}"
    files = {"file": ("pkg.zip", _build_scorm_zip(title), "application/zip")}
    r = admin.post(f"{BASE_URL}/api/admin/scorm/upload", files=files, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == title
    assert body["scorm_version"] == "1.2"
    assert body["launch_url"].startswith("/api/scorm/files/")

    # Serve the index.html
    r2 = requests.get(f"{BASE_URL}{body['launch_url']}", timeout=10)
    assert r2.status_code == 200
    assert "SCORM 1.2 Test" in r2.text


def test_scorm_upload_rejects_non_scorm_zip(admin):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "not scorm")
    files = {"file": ("nope.zip", buf.getvalue(), "application/zip")}
    r = admin.post(f"{BASE_URL}/api/admin/scorm/upload", files=files, timeout=10)
    assert r.status_code == 400
    assert "imsmanifest" in (r.json().get("error", {}).get("message") or r.json().get("detail", "")).lower()


def test_scorm_upload_rejects_traversal(admin):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../etc/escape", "x")
        zf.writestr("imsmanifest.xml", "<manifest/>")
    files = {"file": ("evil.zip", buf.getvalue(), "application/zip")}
    r = admin.post(f"{BASE_URL}/api/admin/scorm/upload", files=files, timeout=10)
    assert r.status_code == 400


def test_xapi_post_and_list(admin):
    payload = {
        "actor": {"mbox": "mailto:admin@ifpi.org", "name": "IFPI Admin"},
        "verb": {"id": "http://adlnet.gov/expapi/verbs/answered"},
        "object": {"id": f"http://test.example/q/{uuid.uuid4().hex}"},
        "result": {"success": True, "score": {"raw": 8, "max": 10}},
    }
    r = admin.post(f"{BASE_URL}/api/xapi/statements", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert isinstance(sid, int)

    # List filtered by verb
    lst = admin.get(
        f"{BASE_URL}/api/xapi/statements?verb=http://adlnet.gov/expapi/verbs/answered&limit=5",
        timeout=10,
    ).json()
    assert any(s["id"] == sid for s in lst["items"])


# ── Iter 19: Slide versioning + rich-text sanitizer ──────────────────
def test_slide_versioning_snapshot_and_restore(admin):
    # Find a slide we can edit
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slide = course["slides"][0]
    sid = slide["id"]

    # Capture original to restore at end
    orig_title = slide["title"]
    orig_content = slide.get("content") or ""

    # Edit twice
    admin.patch(f"{BASE_URL}/api/courses/1/slides/{sid}",
                json={"title": "V-A", "content": "<p>A</p>",
                      "slide_type": "TEXT", "is_required": True}, timeout=10)
    admin.patch(f"{BASE_URL}/api/courses/1/slides/{sid}",
                json={"title": "V-B", "content": "<p>B</p>",
                      "slide_type": "TEXT", "is_required": True}, timeout=10)

    # Versions should reflect the pre-edit snapshots
    versions = admin.get(f"{BASE_URL}/api/courses/1/slides/{sid}/versions", timeout=10).json()
    assert versions["items"], "expected at least one version"
    assert versions["items"][0]["version_number"] > versions["items"][-1]["version_number"], \
        "list should be descending"

    # Restore to the earliest version (the very first pre-edit snapshot)
    earliest = min(v["version_number"] for v in versions["items"])
    r = admin.post(f"{BASE_URL}/api/courses/1/slides/{sid}/versions/{earliest}/restore", timeout=10)
    assert r.status_code == 200, r.text
    # Confirm slide reflects restored title (NOT V-B)
    cur = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    cur_slide = next(s for s in cur["slides"] if s["id"] == sid)
    assert cur_slide["title"] != "V-B"

    # Cleanup — restore original
    admin.patch(f"{BASE_URL}/api/courses/1/slides/{sid}",
                json={"title": orig_title, "content": orig_content,
                      "slide_type": "TEXT", "is_required": True}, timeout=10)


def test_rich_text_sanitizer_strips_script_and_js_uris(admin):
    payload = {"html": '<p>hi <script>alert(1)</script></p>'
                       '<a href="javascript:alert(1)">x</a>'
                       '<img src="x.png" onerror="alert(1)">'}
    r = admin.post(f"{BASE_URL}/api/rich-text/sanitize", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    out = r.json()["sanitized"]
    assert "<script" not in out.lower()
    assert "onerror" not in out.lower()
    assert "javascript:" not in out.lower()


def test_rich_text_requires_admin():
    r = requests.post(f"{BASE_URL}/api/rich-text/sanitize",
                      json={"html": "<p>x</p>"}, timeout=10)
    assert r.status_code in (401, 403)


# ── Iter 17 improvement: ImportJob rollback ───────────────────────────
def _build_content_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        title = f"Rollback Test {uuid.uuid4().hex[:6]}"
        zf.writestr("content/courses/rb_course/course.json",
                    f'{{"title":"{title}","description":"rollback test","category":"test"}}')
        zf.writestr("content/courses/rb_course/slide_01.md", "# Hi\nRollback me.")
    return buf.getvalue()


def test_import_rollback_deletes_created_courses(admin):
    import time
    # Trigger an import via ZIP
    data = _build_content_zip()
    files = {"file": ("content.zip", data, "application/zip")}
    r = admin.post(f"{BASE_URL}/api/admin/imports/upload-zip", files=files, timeout=20)
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]

    # Wait until completed
    deadline = time.time() + 15
    while time.time() < deadline:
        j = admin.get(f"{BASE_URL}/api/admin/imports/{job_id}", timeout=10).json()
        if j["status"] == "COMPLETED":
            break
        time.sleep(0.5)
    assert j["status"] == "COMPLETED", j
    created = [c["id"] for c in (j["results"] or {}).get("courses", [])]
    assert created, "expected at least one created course"

    # Rollback
    rb = admin.post(f"{BASE_URL}/api/admin/imports/{job_id}/rollback", timeout=15)
    assert rb.status_code == 200, rb.text
    body = rb.json()
    assert body["deleted_courses"] == len(created)

    # Verify courses 404
    for cid in created:
        r2 = admin.get(f"{BASE_URL}/api/courses/{cid}", timeout=10)
        assert r2.status_code == 404, f"course {cid} should be gone, got {r2.status_code}"

    # Job marked ROLLED_BACK
    j2 = admin.get(f"{BASE_URL}/api/admin/imports/{job_id}", timeout=10).json()
    assert j2["status"] == "ROLLED_BACK"


def test_rollback_rejected_on_pending(admin):
    """A job that is not COMPLETED/PARTIAL cannot be rolled back."""
    # Find a non-completed job, or skip
    items = admin.get(f"{BASE_URL}/api/admin/imports?limit=50", timeout=10).json()["items"]
    pending = next((j for j in items if j["status"] in ("PENDING", "RUNNING")), None)
    if not pending:
        pytest.skip("no PENDING/RUNNING job available to test rejection path")
    r = admin.post(f"{BASE_URL}/api/admin/imports/{pending['id']}/rollback", timeout=10)
    assert r.status_code == 400
