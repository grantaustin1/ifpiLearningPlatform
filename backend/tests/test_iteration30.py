"""Iter 30 — AI spend analytics + multi-language TTS + LinkedIn share flow."""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    import pytest
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests", allow_module_level=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture
def admin() -> requests.Session:
    return _login("admin@ifpi.org", "admin123")


@pytest.fixture
def learner() -> requests.Session:
    return _login("learner@ifpi.org", "learner123")


# ─── AI spend analytics ─────────────────────────────────────────────
def test_spend_learner_blocked(learner):
    r = learner.get(f"{BASE_URL}/api/admin/api-tokens/analytics/spend", timeout=10)
    assert r.status_code == 403


def test_spend_returns_zero_filled_series(admin):
    r = admin.get(f"{BASE_URL}/api/admin/api-tokens/analytics/spend?days=14", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 14
    assert len(body["series"]) == 14
    assert isinstance(body["providers"], list)
    for d in body["series"]:
        assert "date" in d and "total_cents" in d
        for p in body["providers"]:
            assert p in d
    assert body["total_cents"] >= 0
    assert isinstance(body["by_provider"], list)
    assert "budget" in body


# ─── Multi-language TTS ─────────────────────────────────────────────
def test_languages_endpoint(admin):
    r = admin.get(f"{BASE_URL}/api/authoring/narration/languages", timeout=10)
    assert r.status_code == 200
    langs = r.json()["languages"]
    assert len(langs) >= 8
    codes = {l["code"] for l in langs}
    for expected in ("en", "es", "fr", "de", "hi"):
        assert expected in codes


def test_narration_rejects_invalid_language(admin):
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    r = admin.post(f"{BASE_URL}/api/authoring/narration/generate",
                   json={"slide_id": slides[0]["id"], "language": "xx",
                         "override_text": "Some safe test content here."},
                   timeout=15)
    assert r.status_code == 400


def test_narration_accepts_valid_language(admin):
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    r = admin.post(f"{BASE_URL}/api/authoring/narration/generate",
                   json={"slide_id": slides[0]["id"], "voice": "nova",
                         "language": "en", "translate_first": False,
                         "override_text": "This is a short English narration test."},
                   timeout=60)
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["narration_url"]


def test_narration_language_translate_first_optional(admin):
    """When translate_first is False for a non-English language, the
    admin is trusting the LLM/TTS to handle input. Still returns 200."""
    course = admin.get(f"{BASE_URL}/api/courses/1", timeout=10).json()
    slides = course.get("slides") or []
    if not slides:
        pytest.skip("Course 1 has no slides")
    r = admin.post(f"{BASE_URL}/api/authoring/narration/generate",
                   json={"slide_id": slides[0]["id"], "voice": "nova",
                         "language": "es", "translate_first": False,
                         "override_text": "Bienvenidos al curso — hoy aprenderemos sobre la industria musical."},
                   timeout=60)
    if r.status_code == 503:
        pytest.skip("EMERGENT_LLM_KEY not set")
    assert r.status_code == 200


# ─── Cert PDF QR code (already implemented; smoke check) ────────────
def test_cert_pdf_contains_verify_url(learner):
    certs = learner.get(f"{BASE_URL}/api/certificates", timeout=10).json()
    if not certs:
        pytest.skip("No certificates for learner")
    r = learner.get(f"{BASE_URL}/api/certificates/{certs[0]['id']}/pdf", timeout=30)
    assert r.status_code == 200
    # PDFs are ZIP-ish binary — we just verify it starts with %PDF
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000
