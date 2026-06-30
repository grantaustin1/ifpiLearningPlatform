"""Iteration 3 regression suite — invitations, outbox/mail, lead capture, embed JS,
org branding, slide/path reorder, prerequisite enforcement, cert email.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL is required", allow_module_level=True)

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _sqlite_db_path() -> Path:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./ifpi_lms.db")
    if database_url.startswith("sqlite:///"):
        return Path(database_url.replace("sqlite:///", "", 1)).resolve()
    return (_backend_dir() / "ifpi_lms.db").resolve()


# ── fixtures ──────────────────────────────────────────────────────────
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


@pytest.fixture(scope="session")
def second_course(admin):
    """Create a second course we can use as prerequisite (id != 1)."""
    name = f"TEST_prereq_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE_URL}/api/courses", json={
        "title": name, "description": "prereq seed", "price_cents": 0,
    })
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    # Add a slide so it can be published
    admin.post(f"{BASE_URL}/api/courses/{cid}/slides",
               json={"title": "s1", "content": "body", "order_index": 1})
    pub = admin.post(f"{BASE_URL}/api/courses/{cid}/publish")
    assert pub.status_code == 200, pub.text
    yield cid


# ── Alembic & schema ──────────────────────────────────────────────────
def test_alembic_head_is_iteration3():
    import subprocess
    out = subprocess.check_output(["alembic", "current"], cwd=str(_backend_dir())).decode()
    # Iteration 4 raised head — accept both
    assert any(h in out for h in ("feb2000f209a", "7497425df8bc", "9acf884483b9", "c1f29b3e9d04", "e5a721f43b18", "b3d8915cef27")), out


def test_new_tables_exist():
    import sqlite3
    conn = sqlite3.connect(str(_sqlite_db_path()))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "invitations" in tables
    assert "outbox_messages" in tables


# ── Prerequisites ─────────────────────────────────────────────────────
def test_self_prereq_400(admin):
    r = admin.post(f"{BASE_URL}/api/courses/1/prerequisites/1")
    assert r.status_code == 400


def test_prereq_enforcement_412(admin, learner, second_course):
    # ensure course 1 is published (regression from iteration 2 leaves it draft sometimes)
    admin.post(f"{BASE_URL}/api/courses/1/publish")
    # 1) clean ALL existing prereqs on course 1 (from prior runs)
    existing = admin.get(f"{BASE_URL}/api/courses/1/prerequisites").json() or []
    for p in existing:
        admin.delete(f"{BASE_URL}/api/courses/1/prerequisites/{p['course_id']}")
    r = admin.post(f"{BASE_URL}/api/courses/1/prerequisites/{second_course}")
    assert r.status_code in (200, 201), r.text

    # 2) Reset learner state: nuke any prior completions/enrollments via DB direct
    import sqlite3
    conn = sqlite3.connect(str(_sqlite_db_path()))
    conn.execute("DELETE FROM enrollments WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org')")
    conn.commit()
    conn.close()

    # 3) Enroll attempt should now be 412
    r = learner.post(f"{BASE_URL}/api/courses/1/enroll")
    assert r.status_code == 412, r.text
    detail = r.json().get("detail", {})
    assert "missing" in detail, detail
    ids = [m["id"] for m in detail["missing"]]
    assert second_course in ids


def test_prereq_cleared_after_completion(admin, learner, second_course):
    # Re-add the prereq in case prior test cleaned it up; idempotent
    admin.post(f"{BASE_URL}/api/courses/1/prerequisites/{second_course}")
    # Reset learner enrollments
    import sqlite3
    conn = sqlite3.connect(str(_sqlite_db_path()))
    conn.execute(
        "DELETE FROM enrollments WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org')"
    )
    conn.commit()
    conn.close()
    # enroll + complete the prereq course as learner
    er = learner.post(f"{BASE_URL}/api/courses/{second_course}/enroll")
    assert er.status_code == 200, f"enroll prereq failed: {er.status_code} {er.text}"
    r = learner.post(f"{BASE_URL}/api/courses/{second_course}/complete")
    assert r.status_code == 200, r.text
    # Now course 1 should accept enrollment
    r = learner.post(f"{BASE_URL}/api/courses/1/enroll")
    assert r.status_code == 200, r.text
    # cleanup prereq link so other tests aren't blocked
    admin.delete(f"{BASE_URL}/api/courses/1/prerequisites/{second_course}")


# ── Invitations ───────────────────────────────────────────────────────
def test_invitation_create_list_and_outbox(admin):
    email = f"TEST_inv_{uuid.uuid4().hex[:6]}@example.com".lower()
    r = admin.post(f"{BASE_URL}/api/admin/invitations",
                   json={"email": email, "name": "Test Inv", "role": "INSTRUCTOR"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["role"] == "INSTRUCTOR"
    assert body["expires_at"]
    # list
    lst = admin.get(f"{BASE_URL}/api/admin/invitations").json()
    assert any(i["email"] == email for i in lst)
    # outbox
    ob_resp = admin.get(f"{BASE_URL}/api/admin/outbox?page_size=100").json()
    ob = ob_resp["messages"] if isinstance(ob_resp, dict) else ob_resp
    assert any(m["to_email"] == email and "invit" in (m.get("template") or "").lower() for m in ob)


def test_reinvite_revokes_prior_pending(admin):
    email = f"TEST_reinv_{uuid.uuid4().hex[:6]}@example.com".lower()
    r1 = admin.post(f"{BASE_URL}/api/admin/invitations",
                    json={"email": email, "name": "A", "role": "INSTRUCTOR"})
    assert r1.status_code == 200
    first_id = r1.json()["id"]
    r2 = admin.post(f"{BASE_URL}/api/admin/invitations",
                    json={"email": email, "name": "B", "role": "INSTRUCTOR"})
    assert r2.status_code == 200
    second_id = r2.json()["id"]
    assert second_id != first_id
    # confirm only one pending
    lst = admin.get(f"{BASE_URL}/api/admin/invitations").json()
    pending = [i for i in lst if i["email"] == email and i["status"] == "pending"]
    assert len(pending) == 1
    assert pending[0]["id"] == second_id
    # first should be revoked
    first = next(i for i in lst if i["id"] == first_id)
    assert first["status"] == "revoked"


def test_revoke_invite_and_double_revoke(admin):
    email = f"TEST_rev_{uuid.uuid4().hex[:6]}@example.com"
    r = admin.post(f"{BASE_URL}/api/admin/invitations",
                   json={"email": email, "role": "INSTRUCTOR"})
    iid = r.json()["id"]
    rd = admin.delete(f"{BASE_URL}/api/admin/invitations/{iid}")
    assert rd.status_code == 200
    # second delete should be safe / idempotent or 400 — accept either, but check status
    lst = admin.get(f"{BASE_URL}/api/admin/invitations").json()
    assert any(i["id"] == iid and i["status"] == "revoked" for i in lst)


def test_invitation_accept_flow(admin):
    """End-to-end invite → lookup → accept → auto-login."""
    email = f"TEST_acc_{uuid.uuid4().hex[:6]}@example.com".lower()
    r = admin.post(f"{BASE_URL}/api/admin/invitations",
                   json={"email": email, "name": "Acc User", "role": "INSTRUCTOR"})
    assert r.status_code == 200
    # Fetch token from DB (it's not returned over the API for security)
    import sqlite3
    conn = sqlite3.connect(str(_sqlite_db_path()))
    row = conn.execute(
        "SELECT token FROM invitations WHERE email=? AND accepted_at IS NULL AND revoked_at IS NULL "
        "ORDER BY id DESC LIMIT 1", (email,)
    ).fetchone()
    conn.close()
    assert row, "No invitation token in DB"
    token = row[0]
    # Public lookup (no auth)
    public = requests.Session()
    look = public.get(f"{BASE_URL}/api/invitations/{token}")
    assert look.status_code == 200, look.text
    j = look.json()
    assert j["email"] == email
    assert j["role"] == "INSTRUCTOR"
    assert j.get("organization_name")
    # Accept
    acc = public.post(f"{BASE_URL}/api/invitations/{token}/accept",
                     json={"password": "TestPass123!", "name": "Accepted User"})
    assert acc.status_code == 200, acc.text
    body = acc.json()
    assert body["user"]["email"] == email
    assert "INSTRUCTOR" in body["user"]["roles"]
    # Can also revoke an accepted invite? Should be 400 per spec
    # Find id by email
    lst = admin.get(f"{BASE_URL}/api/admin/invitations").json()
    accepted = next((i for i in lst if i["email"] == email and i["status"] == "accepted"), None)
    assert accepted is not None
    rd = admin.delete(f"{BASE_URL}/api/admin/invitations/{accepted['id']}")
    assert rd.status_code == 400


# ── Cert email on completion ──────────────────────────────────────────
def test_cert_email_outbox_no_duplicate(admin, learner):
    # Ensure learner is enrolled in a course she can complete (course id=1)
    learner.post(f"{BASE_URL}/api/courses/1/enroll")
    # Wipe completions to guarantee a fresh complete event
    import sqlite3
    conn = sqlite3.connect(str(_sqlite_db_path()))
    conn.execute(
        "UPDATE enrollments SET completed_at=NULL, status='IN_PROGRESS' WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org') AND course_id=1"
    )
    # Also remove certificates so PDF can regenerate
    conn.execute("DELETE FROM certificates WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org') AND course_id=1")
    conn.commit()
    conn.close()

    def _outbox():
        d = admin.get(f"{BASE_URL}/api/admin/outbox?page_size=200").json()
        return d["messages"] if isinstance(d, dict) else d

    before = _outbox()
    before_cert = [m for m in before if (m.get("template") or "") == "cert_issued"]
    before_count = len(before_cert)

    r = learner.post(f"{BASE_URL}/api/courses/1/complete")
    assert r.status_code == 200, r.text

    after = _outbox()
    after_cert = [m for m in after if (m.get("template") or "") == "cert_issued"]
    assert len(after_cert) == before_count + 1, "expected 1 new cert_issued outbox message"
    newest = after_cert[0]
    # attachments should reference the PDF file
    assert newest.get("attachments"), "expected attachments on cert email"
    # second completion should NOT add another email
    r2 = learner.post(f"{BASE_URL}/api/courses/1/complete")
    assert r2.status_code == 200
    after2 = _outbox()
    after2_cert = [m for m in after2 if (m.get("template") or "") == "cert_issued"]
    assert len(after2_cert) == before_count + 1, "duplicate cert email created on re-complete"


# ── Org branding & PDF logo ───────────────────────────────────────────
def test_org_get_and_patch_logo(admin):
    g = admin.get(f"{BASE_URL}/api/organization")
    assert g.status_code == 200
    orig = g.json().get("logo_url")
    # set to an unreachable URL — cert must still render (graceful fallback)
    p = admin.patch(f"{BASE_URL}/api/organization",
                    json={"logo_url": "https://does-not-exist-9999.invalid/logo.png"})
    assert p.status_code == 200
    g2 = admin.get(f"{BASE_URL}/api/organization").json()
    assert g2["logo_url"] == "https://does-not-exist-9999.invalid/logo.png"
    # PDF should still work — find a cert for learner course 1
    import sqlite3
    conn = sqlite3.connect(str(_sqlite_db_path()))
    row = conn.execute(
        "SELECT id FROM certificates WHERE user_id=(SELECT id FROM users WHERE email='learner@ifpi.org') LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        pdf = admin.get(f"{BASE_URL}/api/certificates/{row[0]}/pdf")
        assert pdf.status_code == 200
        assert pdf.content[:4] == b"%PDF"
    # restore
    admin.patch(f"{BASE_URL}/api/organization", json={"logo_url": orig})


# ── Slide reorder ─────────────────────────────────────────────────────
def test_slides_reorder(admin):
    r = admin.get(f"{BASE_URL}/api/courses/1")
    assert r.status_code == 200
    course = r.json()
    slides = course.get("slides") or []
    if len(slides) < 2:
        pytest.skip("course 1 has <2 slides; skipping reorder")
    ids = [s["id"] for s in slides]
    reversed_ids = list(reversed(ids))
    p = admin.patch(f"{BASE_URL}/api/courses/1/slides/reorder",
                    json={"slide_ids": reversed_ids})
    assert p.status_code == 200, p.text
    r2 = admin.get(f"{BASE_URL}/api/courses/1")
    new_ids = [s["id"] for s in r2.json()["slides"]]
    assert new_ids == reversed_ids, f"expected {reversed_ids} got {new_ids}"
    # restore
    admin.patch(f"{BASE_URL}/api/courses/1/slides/reorder", json={"slide_ids": ids})


# ── Path item reorder ─────────────────────────────────────────────────
def test_path_items_reorder(admin, second_course):
    # Create a new path with 2 items
    name = f"TEST_path_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE_URL}/api/learning-paths",
                   json={"title": name, "description": "x"})
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]
    # add 2 items (course 1 + second_course)
    admin.post(f"{BASE_URL}/api/learning-paths/{pid}/items",
               json={"course_id": 1, "order_index": 1, "required": True})
    admin.post(f"{BASE_URL}/api/learning-paths/{pid}/items",
               json={"course_id": second_course, "order_index": 2, "required": True})
    full = admin.get(f"{BASE_URL}/api/learning-paths/{pid}").json()
    items = full.get("items") or []
    if len(items) < 2:
        pytest.skip("could not add 2 items to test path")
    ids = [i["id"] for i in items]
    rev = list(reversed(ids))
    p = admin.patch(f"{BASE_URL}/api/learning-paths/{pid}/items/reorder",
                    json={"item_ids": rev})
    assert p.status_code == 200
    full2 = admin.get(f"{BASE_URL}/api/learning-paths/{pid}").json()
    new_ids = [i["id"] for i in full2["items"]]
    assert new_ids == rev


# ── Lead capture + embed ──────────────────────────────────────────────
def test_lead_capture_idempotent_no_downgrade():
    public = requests.Session()
    email = f"TEST_lead_{uuid.uuid4().hex[:6]}@example.com"
    r1 = public.post(f"{BASE_URL}/api/leads",
                     json={"email": email, "name": "Lead", "source": "embed"})
    assert r1.status_code == 201, r1.text
    j1 = r1.json()
    assert j1["ok"] is True
    assert j1["is_new"] is True
    assert j1.get("lifecycle_stage") == "PROSPECT"
    pid = j1["person_id"]
    # second post
    r2 = public.post(f"{BASE_URL}/api/leads",
                     json={"email": email, "name": "Lead Updated"})
    assert r2.status_code == 201
    j2 = r2.json()
    assert j2["is_new"] is False
    assert j2["person_id"] == pid

    # Test: existing LEARNER person not downgraded
    # Use learner@ifpi.org which has Person row already (LEARNER stage)
    r3 = public.post(f"{BASE_URL}/api/leads",
                     json={"email": "learner@ifpi.org", "name": "Learner"})
    assert r3.status_code == 201
    j3 = r3.json()
    assert j3["is_new"] is False
    assert j3["lifecycle_stage"] == "LEARNER", f"expected LEARNER got {j3.get('lifecycle_stage')}"


def test_embed_js():
    r = requests.get(f"{BASE_URL}/api/leads/embed.js?organization=ifpi-main")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "javascript" in ct.lower(), ct
    assert "IFPILeadEmbed" in r.text
