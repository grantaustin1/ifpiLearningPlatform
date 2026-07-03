"""Iteration 5: cert preview, file uploads, slide comments, academies, public portal."""
import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


# ── Shared fixtures ──────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"})
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture(scope="module")
def learner_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": "learner@ifpi.org", "password": "learner123"})
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


# ── Login + cookies ──────────────────────────────────────────────────
def test_admin_login_returns_user_and_cookies():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert "user" in data
    assert data["user"]["email"] == "admin@ifpi.org"
    cookie_names = {c.name for c in s.cookies}
    assert any("access" in n.lower() or "token" in n.lower() for n in cookie_names), \
        f"No auth cookie found, got: {cookie_names}"


# ── Public portal ────────────────────────────────────────────────────
def test_public_portal_no_auth():
    r = requests.get(f"{API}/portal/ifpi-main")
    assert r.status_code == 200
    data = r.json()
    assert data["organization"]["slug"] == "ifpi-main"
    assert "stats" in data and "courses" in data
    assert isinstance(data["courses"], list)


def test_public_portal_unknown_slug():
    r = requests.get(f"{API}/portal/does-not-exist-zzzzz")
    assert r.status_code == 404


# ── Slide comments ───────────────────────────────────────────────────
def test_slide_comments_crud(learner_session):
    slide_id = 1
    body = f"TEST_comment_{uuid.uuid4().hex[:8]}"
    # POST
    r = learner_session.post(f"{API}/slides/{slide_id}/comments",
                             json={"body": body})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["body"] == body
    assert c["slide_id"] == slide_id
    cid = c["id"]
    # GET list contains it
    r = learner_session.get(f"{API}/slides/{slide_id}/comments")
    assert r.status_code == 200
    assert any(x["id"] == cid for x in r.json())
    # DELETE own
    r = learner_session.delete(f"{API}/slides/{slide_id}/comments/{cid}")
    assert r.status_code == 200
    # GET list no longer contains it (soft-delete filter)
    r = learner_session.get(f"{API}/slides/{slide_id}/comments")
    assert not any(x["id"] == cid for x in r.json())


def test_slide_comment_empty_body_400(learner_session):
    r = learner_session.post(f"{API}/slides/1/comments", json={"body": "  "})
    assert r.status_code == 400


def test_slide_comment_invalid_slide_404(learner_session):
    r = learner_session.post(f"{API}/slides/999999/comments",
                             json={"body": "x"})
    assert r.status_code == 404


# ── Cert preview ─────────────────────────────────────────────────────
def test_cert_preview_admin_returns_pdf(admin_session):
    r = admin_session.post(f"{API}/admin/cert-preview", json={
        "organisation_name": "TEST_Preview Academy",
        "accent_color": "#10b981",
        "signature_text": "Test Signatory",
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_cert_preview_learner_forbidden(learner_session):
    r = learner_session.post(f"{API}/admin/cert-preview", json={})
    assert r.status_code == 403


# ── File upload ──────────────────────────────────────────────────────
# 1x1 PNG generated via PIL
def _make_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()

PNG_BYTES = _make_png()


def test_image_upload_admin_then_serve(admin_session):
    files = {"file": ("test.png", io.BytesIO(PNG_BYTES), "image/png")}
    r = admin_session.post(f"{API}/uploads/image", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data and ("key" in data or "filename" in data) and "size" in data
    assert data["size"] == len(PNG_BYTES)
    # GET that URL returns same bytes — url is relative under the new
    # storage abstraction (resolves through the ingress).
    full_url = data["url"] if data["url"].startswith("http") else f"{BASE_URL}{data['url']}"
    r2 = requests.get(full_url)
    assert r2.status_code == 200
    assert r2.headers["content-type"].startswith("image/png")
    assert r2.content == PNG_BYTES


def test_image_upload_rejects_non_image(admin_session):
    files = {"file": ("evil.txt", io.BytesIO(b"hello"), "text/plain")}
    r = admin_session.post(f"{API}/uploads/image", files=files)
    assert r.status_code == 400


def test_image_upload_rejects_too_large(admin_session):
    # 6 MB blob with PNG mime
    big = b"\x00" * (6 * 1024 * 1024)
    files = {"file": ("big.png", io.BytesIO(big), "image/png")}
    r = admin_session.post(f"{API}/uploads/image", files=files)
    assert r.status_code == 413


def test_image_upload_learner_forbidden(learner_session):
    files = {"file": ("test.png", io.BytesIO(PNG_BYTES), "image/png")}
    r = learner_session.post(f"{API}/uploads/image", files=files)
    assert r.status_code == 403


# ── Academies (SUPER_ADMIN) ──────────────────────────────────────────
def test_academies_list_as_super_admin(admin_session):
    # admin@ifpi.org has both ADMIN and SUPER_ADMIN roles in this env
    r = admin_session.get(f"{API}/academies")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    assert any(o["slug"] == "ifpi-main" for o in rows)


def test_academies_list_as_learner_forbidden(learner_session):
    r = learner_session.get(f"{API}/academies")
    assert r.status_code == 403


def test_create_academy_queues_invitation(admin_session):
    suffix = uuid.uuid4().hex[:8]
    slug = f"test-acad-{suffix}"
    email = f"TEST_acad_admin_{suffix}@example.com"
    import sys
    sys.path.insert(0, "/app/backend")
    from core.database import SessionLocal
    from models import OutboxMessage

    r = admin_session.post(f"{API}/academies", json={
        "name": f"TEST Academy {suffix}",
        "slug": slug,
        "admin_email": email,
        "admin_name": "Test Admin",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["slug"] == slug
    assert data["admin_invited"] == email
    new_org_id = data["academy_id"]

    # Outbox row should have been queued for the new academy (in its org)
    db = SessionLocal()
    inv_msg = db.query(OutboxMessage).filter(
        OutboxMessage.to_email == email.lower(),
        OutboxMessage.template == "invitation",
    ).first()
    db.close()
    assert inv_msg is not None, "No invitation outbox row created for new academy"
    assert inv_msg.organization_id == new_org_id

    # Duplicate slug rejected
    r = admin_session.post(f"{API}/academies", json={
        "name": "dup", "slug": slug, "admin_email": email,
    })
    assert r.status_code == 400


# ── Outbox retry + worker drains ─────────────────────────────────────
def test_outbox_stats_endpoint(admin_session):
    r = admin_session.get(f"{API}/admin/outbox/stats")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_outbox_retry_and_worker_drains(admin_session):
    """Tests POST /api/admin/outbox/{id}/retry (resets FAILED→QUEUED) + worker drain."""
    # Find or force a FAILED row by manipulating DB directly
    import sys
    sys.path.insert(0, "/app/backend")
    from core.database import SessionLocal
    from models import OutboxMessage

    db = SessionLocal()
    msg = OutboxMessage(
        to_email="test_retry@example.com", to_name="t",
        subject="TEST retry", body_html="x", body_text="x",
        template="generic", status="FAILED", attempt_count=1,
        error="forced failure for test", organization_id=1,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    mid = msg.id
    db.close()

    r = admin_session.post(f"{API}/admin/outbox/{mid}/retry")
    if r.status_code == 404:
        pytest.fail(f"POST /api/admin/outbox/{mid}/retry endpoint MISSING — required by review request")
    assert r.status_code == 200, r.text

    # Worker drains within ~10s
    drained = False
    last = None
    for _ in range(15):
        db = SessionLocal()
        row = db.query(OutboxMessage).filter(OutboxMessage.id == mid).first()
        last = row.status if row else None
        db.close()
        if last in {"SENT", "STUB"}:
            drained = True
            break
        time.sleep(1)
    assert drained, f"Worker did not drain msg {mid}; last status={last}"


# ── Regression: courses CRUD still works ─────────────────────────────
def test_course_duplicate_regression(admin_session):
    r = admin_session.post(f"{API}/courses/1/duplicate")
    assert r.status_code == 200
    new_id = r.json().get("id") or r.json().get("course_id")
    assert new_id
    # cleanup
    admin_session.delete(f"{API}/courses/{new_id}")


def test_course_publish_unpublish_regression(admin_session):
    # find a draft course or use course 1 - just check endpoint exists
    r = admin_session.post(f"{API}/courses/1/unpublish")
    assert r.status_code in (200, 400)
    r = admin_session.post(f"{API}/courses/1/publish")
    assert r.status_code in (200, 400)


def test_prerequisites_regression(admin_session):
    r = admin_session.get(f"{API}/courses/1/prerequisites")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
