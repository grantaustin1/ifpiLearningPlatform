"""Iter 33c — Docs engagement tile endpoint tests.

Verifies the /api/admin/dashboard/docs-engagement roll-up:
  - admin-only (learner gets 403)
  - counts DOC_PREVIEWED + DOC_DOWNLOADED events in the last N days
  - returns top_docs sorted desc with pretty titles

We drive events by hitting the real /api/admin/docs/{slug}/pdf endpoint
which writes to the audit log (see routers/docs_library.py).
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
    assert r.status_code == 200, r.text
    body = r.json()
    if body.get("requires_2fa"):
        pytest.skip("Admin account has 2FA — disable it before running these tests")
    # Session cookies from login are carried automatically; also set
    # Authorization if a bearer token is returned (test-only mode).
    token = body.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture
def admin():
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner():
    return _login("learner@ifpi.org", "learner123")


def test_learner_forbidden(learner):
    r = learner.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement", timeout=10)
    assert r.status_code == 403, r.text


def test_engagement_shape_and_rollup(admin):
    # Drive a preview + download for two distinct docs so we have data
    # to roll up. Docs endpoints are audit-logged synchronously.
    for slug in ("setup-manual", "user-manual"):
        p = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf?preview=true",
                      timeout=30)
        assert p.status_code == 200, p.text
        d = admin.get(f"{BASE_URL}/api/admin/docs/{slug}/pdf", timeout=30)
        assert d.status_code == 200, d.text

    # Give the DB a beat (audit rows are committed synchronously so 0 wait
    # is usually fine, but be defensive under CI load)
    time.sleep(0.2)

    r = admin.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement?days=7",
                  timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()

    # Shape
    for key in ("window_days", "total_events", "unique_docs",
                "unique_readers", "top_docs", "latest_at"):
        assert key in data, f"missing key {key} in {data.keys()}"
    assert data["window_days"] == 7
    assert isinstance(data["top_docs"], list)

    # Counts — we fired 4 events (2 previews + 2 downloads) for THIS admin
    assert data["total_events"] >= 4, data
    assert data["unique_docs"] >= 2, data
    assert data["unique_readers"] >= 1, data

    # top_docs sorted desc, first entry has the higher count
    if len(data["top_docs"]) >= 2:
        assert data["top_docs"][0]["count"] >= data["top_docs"][1]["count"]

    # Titles look human (not the slug)
    slugs = {d["slug"] for d in data["top_docs"]}
    assert "setup-manual" in slugs or "user-manual" in slugs, data["top_docs"]
    for d in data["top_docs"]:
        if d["slug"] == "setup-manual":
            assert "Setup" in d["title"]
        if d["slug"] == "user-manual":
            assert "User" in d["title"]


def test_empty_window(admin):
    # A 0-day window is rejected (Query ge=1), so use days=1 with a
    # tight time bound — we cannot easily assert exact zero without
    # nuking the audit log, so just assert the shape holds even when
    # there might be no rows in a stricter window than the fixture.
    r = admin.get(f"{BASE_URL}/api/admin/dashboard/docs-engagement?days=1",
                  timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["window_days"] == 1
    assert isinstance(body["total_events"], int)
    assert body["total_events"] >= 0
