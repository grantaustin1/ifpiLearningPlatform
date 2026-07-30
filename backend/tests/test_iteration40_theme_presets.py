"""Iter 40 — custom theme presets CRUD + fitness rebrand guards."""
from __future__ import annotations

import os

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
        pytest.skip("Admin account has 2FA — clear it first")
    s.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return s


@pytest.fixture
def admin(): return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner(): return _login("learner@ifpi.org", "learner123")


def _cleanup(admin, name_prefix="TEST_iter40"):
    themes = admin.get(f"{BASE_URL}/api/organization/themes", timeout=15).json()
    for t in themes:
        if t.get("custom") and t["name"].startswith(name_prefix):
            admin.delete(f"{BASE_URL}/api/organization/themes/{t['id']}", timeout=15)


def test_builtin_presets_are_neutral(admin):
    themes = admin.get(f"{BASE_URL}/api/organization/themes", timeout=15).json()
    builtins = [t for t in themes if not t.get("custom")]
    assert len(builtins) >= 5
    blob = str(builtins).lower()
    for banned in ("music", "phonographic", "conservatoire", "label academy"):
        assert banned not in blob, f"music-era copy leaked: {banned}"


def test_custom_preset_crud_and_apply(admin):
    _cleanup(admin)
    # create
    r = admin.post(f"{BASE_URL}/api/organization/themes", json={
        "name": "TEST_iter40 Neon", "description": "test preset",
        "primary_color": "#123456", "cert_accent_color": "#654321",
        "cert_signature_text_suggestion": "Head Coach",
        "cert_footer_text_suggestion": "TEST footer",
    }, timeout=15)
    assert r.status_code == 201, r.text
    pid, slug = r.json()["id"], r.json()["slug"]
    assert slug.startswith("custom_")

    # listed with custom flag
    themes = admin.get(f"{BASE_URL}/api/organization/themes", timeout=15).json()
    mine = next(t for t in themes if t.get("id") == pid)
    assert mine["custom"] is True and mine["primary_color"] == "#123456"

    # update
    r = admin.put(f"{BASE_URL}/api/organization/themes/{pid}", json={
        "name": "TEST_iter40 Neon v2", "primary_color": "#222222",
        "cert_accent_color": "#654321",
    }, timeout=15)
    assert r.status_code == 200, r.text

    # apply — org colours change
    r = admin.post(f"{BASE_URL}/api/organization/apply-theme/{slug}", timeout=15)
    assert r.status_code == 200, r.text
    org = admin.get(f"{BASE_URL}/api/organization", timeout=15).json()
    assert org["primary_color"] == "#222222"
    assert org["theme_preset"] == slug

    # restore default + delete
    admin.post(f"{BASE_URL}/api/organization/apply-theme/ifpi_classic", timeout=15)
    r = admin.delete(f"{BASE_URL}/api/organization/themes/{pid}", timeout=15)
    assert r.status_code == 200
    themes = admin.get(f"{BASE_URL}/api/organization/themes", timeout=15).json()
    assert not any(t.get("id") == pid for t in themes)


def test_invalid_colour_rejected(admin):
    r = admin.post(f"{BASE_URL}/api/organization/themes", json={
        "name": "TEST_iter40 Bad", "primary_color": "red",
        "cert_accent_color": "#654321",
    }, timeout=15)
    assert r.status_code == 422


def test_learner_cannot_mutate_presets(learner):
    r = learner.post(f"{BASE_URL}/api/organization/themes", json={
        "name": "TEST_iter40 Nope", "primary_color": "#111111",
        "cert_accent_color": "#222222",
    }, timeout=15)
    assert r.status_code == 403
    r = learner.delete(f"{BASE_URL}/api/organization/themes/999999", timeout=15)
    assert r.status_code == 403


def test_seed_course_is_fitness_branded(learner):
    r = learner.get(f"{BASE_URL}/api/courses", timeout=15)
    assert r.status_code == 200
    fundamentals = [c for c in r.json() if c.get("title") == "IFPI Fundamentals"]
    if not fundamentals:
        pytest.skip("seed course absent in this DB")
    desc = (fundamentals[0].get("description") or "").lower()
    assert "fitness" in desc and "phonographic" not in desc
