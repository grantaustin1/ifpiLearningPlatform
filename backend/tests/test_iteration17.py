"""Iteration 17 — SQL-backed SSO replay store, ZIP upload, storage diagnostics."""
from __future__ import annotations

import io
import os
import time
import uuid
import zipfile

import pytest
import requests
from jose import jwt

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL required"

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


# ── Alembic head ──────────────────────────────────────────────────────
def test_alembic_head_includes_iteration17():
    """The Iter 17 migration must be IN the history (not necessarily head)."""
    import subprocess
    # `alembic history` shows the full chain — Iter 18+ pushes head forward.
    hist = subprocess.check_output(
        ["alembic", "history"], cwd="/app/backend",
    ).decode()
    assert "f1a2b3c4d5e6" in hist, f"sso_jti_seen migration missing from history: {hist[:300]}"


def test_sso_jti_seen_table_exists():
    import sqlite3
    conn = sqlite3.connect("/app/backend/ifpi_lms.db")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "sso_jti_seen" in tables


# ── Storage diagnostics ───────────────────────────────────────────────
def test_storage_info_admin_only(admin):
    r = admin.get(f"{BASE_URL}/api/admin/storage/info", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backend"] in ("local", "s3", "gcs")
    assert "probe" in body
    assert body["probe"]["ok"] is True, body


def test_storage_info_blocks_anonymous():
    r = requests.get(f"{BASE_URL}/api/admin/storage/info", timeout=10)
    assert r.status_code in (401, 403)


# ── ZIP upload + extraction ───────────────────────────────────────────
def _build_zip(course_title: str = "Iter17 ZIP Course") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "content/courses/sample/course.json",
            f'{{"title":"{course_title}","description":"from zip","category":"test"}}',
        )
        zf.writestr("content/courses/sample/slide_01.md", "# hi\nFrom ZIP.")
    return buf.getvalue()


def test_upload_zip_extracts_and_imports(admin):
    data = _build_zip(course_title=f"Iter17 ZIP {uuid.uuid4().hex[:6]}")
    files = {"file": ("content.zip", data, "application/zip")}
    r = admin.post(
        f"{BASE_URL}/api/admin/imports/upload-zip?publish_on_import=false",
        files=files, timeout=30,
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]
    # Poll for completion
    deadline = time.time() + 15
    final = None
    while time.time() < deadline:
        g = admin.get(f"{BASE_URL}/api/admin/imports/{job_id}", timeout=10).json()
        if g["status"] in ("COMPLETED", "PARTIAL", "FAILED"):
            final = g
            break
        time.sleep(0.5)
    assert final is not None, "import job did not complete in 15s"
    assert final["status"] == "COMPLETED", final
    assert final["total_items"] >= 1


def test_upload_zip_rejects_non_zip(admin):
    files = {"file": ("readme.txt", b"not a zip", "text/plain")}
    r = admin.post(f"{BASE_URL}/api/admin/imports/upload-zip", files=files, timeout=10)
    assert r.status_code == 400
    assert "zip" in r.json()["detail"].lower()


def test_upload_zip_rejects_traversal(admin):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../etc/escape.txt", "pwn")
    files = {"file": ("evil.zip", buf.getvalue(), "application/zip")}
    r = admin.post(f"{BASE_URL}/api/admin/imports/upload-zip", files=files, timeout=10)
    assert r.status_code == 400
    assert "unsafe" in r.json()["detail"].lower()


# ── SSO replay protection now persisted in SQL ────────────────────────
@pytest.fixture(scope="module")
def sso_setup(tmp_path_factory):
    """Set up an env-flagged SSO secret on the running server. We assume
    SSO_ENABLED is already true on this server (Iter 14 setup), otherwise
    skip — we are testing the replay store layer, not the full handshake.
    """
    # Probe to learn if SSO is on
    r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                      json={"erp_token": "dummy"}, timeout=10)
    if r.status_code == 503:
        pytest.skip("SSO disabled on this server (SSO_ENABLED != true)")
    return True


def _mint_sso_token(jti: str, secret: str, email: str = "admin@ifpi.org",
                    iat: int | None = None, exp_offset: int = 300) -> str:
    now = int(time.time())
    payload = {
        "iss": "erp360", "aud": "ifpi-lms",
        "sub": "1", "email": email, "name": "SSO Test",
        "iat": iat if iat is not None else now,
        "exp": now + exp_offset,
        "jti": jti, "roles": ["MANAGER"],
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_sso_replay_protection_persists_across_sessions(sso_setup):
    # Read shared secret directly from .env (test-only convenience).
    from pathlib import Path
    env = (Path("/app/backend/.env")).read_text()
    secret = next(
        (line.split("=", 1)[1].strip() for line in env.splitlines()
         if line.startswith("ERP360_SSO_SHARED_SECRET=")),
        None,
    )
    if not secret:
        pytest.skip("ERP360_SSO_SHARED_SECRET not set")

    jti = f"iter17-{uuid.uuid4().hex}"
    token = _mint_sso_token(jti, secret)

    # First exchange — succeeds
    r1 = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                       json={"erp_token": token}, timeout=15)
    assert r1.status_code == 200, r1.text

    # Second exchange with same jti — must be rejected as replay
    r2 = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                       json={"erp_token": token}, timeout=15)
    assert r2.status_code == 401, r2.text
    assert "replay" in r2.json()["detail"].lower()

    # And — the proof of multi-process safety — the row is in SQL,
    # so a fresh DB session sees the marker.
    import sqlite3
    conn = sqlite3.connect("/app/backend/ifpi_lms.db")
    row = conn.execute("SELECT jti FROM sso_jti_seen WHERE jti=?", (jti,)).fetchone()
    conn.close()
    assert row is not None, "jti was not persisted to sso_jti_seen"
