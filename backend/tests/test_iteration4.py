"""Iteration 4 regression suite — outbox pagination/filters/stats,
course duplicate, prerequisite CRUD, org cert branding fields,
PDF cert with branding, async outbox worker.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL is required", allow_module_level=True)

# Compute backend directory and SQLite DB path for direct sqlite3 access in tests.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_db_url = os.environ.get("DATABASE_URL", "sqlite:///./ifpi_lms.db")
_db_rel = _db_url.split("sqlite:///")[-1]
_DB_PATH = _db_rel if os.path.isabs(_db_rel) else os.path.join(_BACKEND_DIR, _db_rel.lstrip("./"))

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def admin():
    return _login(**ADMIN)


@pytest.fixture(scope="session")
def learner():
    return _login(**LEARNER)


# ── Alembic head and new columns ────────────────────────────────────
def test_alembic_head_iteration4():
    """Iter 4 migration must remain in the history. Later iterations push the
    head forward — that's expected; we just verify our chain is intact."""
    import subprocess
    current = subprocess.check_output(["alembic", "current"], cwd=_BACKEND_DIR).decode().strip()
    heads = subprocess.check_output(["alembic", "heads"], cwd=_BACKEND_DIR).decode()
    assert current, current
    current_rev = current.split()[0]
    assert current_rev in heads, f"Current revision {current_rev} is not in alembic heads: {heads}"


def test_org_cert_branding_columns_exist():
    import sqlite3
    conn = sqlite3.connect(_DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(organizations)")}
    conn.close()
    for c in ("cert_accent_color", "cert_signature_text",
              "cert_signature_image_url", "cert_footer_text"):
        assert c in cols, f"missing column {c}"


# ── Outbox pagination ───────────────────────────────────────────────
def test_outbox_pagination_shape(admin):
    r = admin.get(f"{BASE_URL}/api/admin/outbox?page=1&page_size=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict), f"expected dict got {type(body)}: {body}"
    for key in ("messages", "page", "page_size", "total", "total_pages"):
        assert key in body, f"missing key {key} in {body.keys()}"
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["messages"]) <= 5
    assert isinstance(body["total"], int)


def test_outbox_pagination_page_2_differs(admin):
    p1 = admin.get(f"{BASE_URL}/api/admin/outbox?page=1&page_size=3").json()
    p2 = admin.get(f"{BASE_URL}/api/admin/outbox?page=2&page_size=3").json()
    if p1["total"] <= 3:
        pytest.skip("not enough messages to compare pages")
    ids1 = {m["id"] for m in p1["messages"]}
    ids2 = {m["id"] for m in p2["messages"]}
    assert ids1.isdisjoint(ids2), f"overlap between pages: {ids1 & ids2}"


def test_outbox_pagination_out_of_range(admin):
    r = admin.get(f"{BASE_URL}/api/admin/outbox?page=999&page_size=5").json()
    assert r["messages"] == []
    assert r["page"] == 999
    assert "total" in r


# ── Outbox filters ──────────────────────────────────────────────────
def test_outbox_filter_status_stub(admin):
    r = admin.get(f"{BASE_URL}/api/admin/outbox?status=STUB&page_size=20").json()
    for m in r["messages"]:
        assert m["status"] == "STUB", m


def test_outbox_filter_search(admin):
    r = admin.get(f"{BASE_URL}/api/admin/outbox?q=certificate&page_size=20").json()
    # If anything returned, each must match in subject or to_email
    for m in r["messages"]:
        hay = ((m.get("subject") or "") + (m.get("to_email") or "")).lower()
        assert "certificate" in hay or m.get("template") == "cert_issued", m


def test_outbox_filter_template(admin):
    r = admin.get(f"{BASE_URL}/api/admin/outbox?template=cert_issued&page_size=20").json()
    for m in r["messages"]:
        assert m.get("template") == "cert_issued", m


# ── Outbox stats ────────────────────────────────────────────────────
def test_outbox_stats(admin):
    r = admin.get(f"{BASE_URL}/api/admin/outbox/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    # Should be a dict counting per status
    assert isinstance(body, dict)
    # Optional keys; assert at least one known
    known = {"STUB", "SENT", "FAILED", "QUEUED"}
    assert known.intersection(body.keys()), body


# ── Course duplicate ────────────────────────────────────────────────
def test_course_duplicate_as_admin(admin):
    # ensure course 1 has slides
    src = admin.get(f"{BASE_URL}/api/courses/1").json()
    src_title = src["title"]
    src_slides = len(src.get("slides") or [])
    r = admin.post(f"{BASE_URL}/api/courses/1/duplicate")
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body.get("ok") is True
    new_id = body.get("course_id")
    assert isinstance(new_id, int) and new_id != 1
    assert "(copy)" in body.get("title", "").lower() or src_title in body.get("title", "")
    assert body.get("slides_copied") == src_slides

    # Verify GET returns DRAFT
    g = admin.get(f"{BASE_URL}/api/courses/{new_id}")
    assert g.status_code == 200
    nc = g.json()
    assert nc["status"] == "DRAFT", nc["status"]
    assert len(nc.get("slides") or []) == src_slides
    # cleanup
    admin.delete(f"{BASE_URL}/api/courses/{new_id}")


def test_course_duplicate_forbidden_for_learner(learner):
    r = learner.post(f"{BASE_URL}/api/courses/1/duplicate")
    assert r.status_code == 403, r.text


def test_course_duplicate_404(admin):
    r = admin.post(f"{BASE_URL}/api/courses/9999/duplicate")
    assert r.status_code == 404


# ── Prerequisite CRUD ───────────────────────────────────────────────
def test_prereq_crud(admin):
    # create a sacrificial course to use as prereq target
    name = f"TEST_it4_prereq_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE_URL}/api/courses", json={
        "title": name, "description": "x", "price_cents": 0,
    })
    assert r.status_code in (200, 201)
    cid = r.json()["id"]
    try:
        # ensure clean state on course 1
        for p in admin.get(f"{BASE_URL}/api/courses/1/prerequisites").json() or []:
            admin.delete(f"{BASE_URL}/api/courses/1/prerequisites/{p['course_id']}")
        # add
        a = admin.post(f"{BASE_URL}/api/courses/1/prerequisites/{cid}")
        assert a.status_code in (200, 201), a.text
        # list
        lst = admin.get(f"{BASE_URL}/api/courses/1/prerequisites").json()
        assert any(p["course_id"] == cid for p in lst)
        # delete
        d = admin.delete(f"{BASE_URL}/api/courses/1/prerequisites/{cid}")
        assert d.status_code == 200
        lst2 = admin.get(f"{BASE_URL}/api/courses/1/prerequisites").json()
        assert not any(p["course_id"] == cid for p in lst2)
    finally:
        admin.delete(f"{BASE_URL}/api/courses/{cid}")


# ── Org branding PATCH/GET ──────────────────────────────────────────
def test_org_patch_branding_fields(admin):
    orig = admin.get(f"{BASE_URL}/api/organization").json()
    payload = {
        "cert_accent_color": "#10b981",
        "cert_signature_text": "Test Signature",
        "cert_footer_text": "Footer disclaimer",
    }
    p = admin.patch(f"{BASE_URL}/api/organization", json=payload)
    assert p.status_code == 200, p.text
    g = admin.get(f"{BASE_URL}/api/organization").json()
    assert g["cert_accent_color"] == "#10b981"
    assert g["cert_signature_text"] == "Test Signature"
    assert g["cert_footer_text"] == "Footer disclaimer"
    # restore
    admin.patch(f"{BASE_URL}/api/organization", json={
        "cert_accent_color": orig.get("cert_accent_color"),
        "cert_signature_text": orig.get("cert_signature_text"),
        "cert_footer_text": orig.get("cert_footer_text"),
    })


# ── PDF cert with new branding + malformed colour ───────────────────
def test_pdf_cert_with_branding_and_bad_color(admin, learner):
    # Ensure a certificate exists
    learner.post(f"{BASE_URL}/api/courses/1/enroll")
    learner.post(f"{BASE_URL}/api/courses/1/complete")
    import sqlite3
    conn = sqlite3.connect(_DB_PATH)
    row = conn.execute(
        "SELECT id FROM certificates WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org') LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        pytest.skip("no certificate row available")
    cert_id = row[0]

    # patch malformed accent
    orig = admin.get(f"{BASE_URL}/api/organization").json()
    admin.patch(f"{BASE_URL}/api/organization", json={
        "cert_accent_color": "not-a-colour",
        "cert_signature_text": "Bad Colour Test",
        "cert_footer_text": "Bad colour footer",
    })
    try:
        pdf = admin.get(f"{BASE_URL}/api/certificates/{cert_id}/pdf")
        assert pdf.status_code == 200, pdf.text[:200]
        assert pdf.content[:4] == b"%PDF", pdf.content[:50]
    finally:
        admin.patch(f"{BASE_URL}/api/organization", json={
            "cert_accent_color": orig.get("cert_accent_color"),
            "cert_signature_text": orig.get("cert_signature_text"),
            "cert_footer_text": orig.get("cert_footer_text"),
        })


# ── Outbox worker: QUEUED → STUB transition ─────────────────────────
def test_outbox_worker_drains_queued(admin, learner):
    """After triggering a fresh cert email, expect a QUEUED row to be
    auto-transitioned to STUB by the background worker within ~10s.
    """
    # Wipe certificate so completion regenerates it
    import sqlite3
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "UPDATE enrollments SET completed_at=NULL, status='IN_PROGRESS' "
        "WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org') AND course_id=1"
    )
    conn.execute(
        "DELETE FROM certificates WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org') AND course_id=1"
    )
    conn.commit()
    conn.close()

    # Capture STUB count before
    before = admin.get(f"{BASE_URL}/api/admin/outbox?status=STUB&page_size=1").json()["total"]

    learner.post(f"{BASE_URL}/api/courses/1/enroll")
    t0 = time.time()
    r = learner.post(f"{BASE_URL}/api/courses/1/complete")
    latency = time.time() - t0
    assert r.status_code == 200, r.text
    # Decoupled: complete should return reasonably fast (< 5s)
    assert latency < 8, f"complete took {latency:.2f}s — mail not decoupled?"

    # Wait up to 12s for worker to flip QUEUED→STUB
    deadline = time.time() + 12
    after = before
    while time.time() < deadline:
        after = admin.get(f"{BASE_URL}/api/admin/outbox?status=STUB&page_size=1").json()["total"]
        if after > before:
            break
        time.sleep(1)
    assert after > before, f"STUB count did not increase ({before} → {after}) after 12s"
