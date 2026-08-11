"""Iter 23 — source-grounded tutor + Iter 24 Tavily skeleton."""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests", allow_module_level=True)

ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(**ADMIN)


@pytest.fixture(scope="module")
def learner():
    return _login(**LEARNER)


# ── Chunker (unit) ────────────────────────────────────────────────────
def test_chunker_splits_long_text():
    from services.embedding_service import chunk_text
    text = "\n\n".join([f"Paragraph {i} " + "word " * 200 for i in range(20)])
    chunks = chunk_text(text)
    assert len(chunks) > 1
    # No chunk exceeds the hard max
    assert all(len(c) < 5000 for c in chunks)


def test_chunker_handles_short_input():
    from services.embedding_service import chunk_text
    assert chunk_text("") == []
    assert chunk_text("Short.") == ["Short."]


def test_cosine_similarity_basics():
    from services.embedding_service import cosine_similarity
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0], []) == 0.0


# ── Sources CRUD ──────────────────────────────────────────────────────
def test_source_upload_and_list_and_delete(admin):
    title = f"Pytest Source {uuid.uuid4().hex[:6]}"
    r = admin.post(
        f"{BASE_URL}/api/authoring/sources",
        files={"file": ("test.txt", b"This is a test document about test topics.", "text/plain")},
        data={"title": title},
        timeout=60,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["title"] == title
    assert doc["chunk_count"] >= 1
    doc_id = doc["id"]

    lst = admin.get(f"{BASE_URL}/api/authoring/sources", timeout=10).json()
    assert any(d["id"] == doc_id for d in lst["items"])

    d = admin.delete(f"{BASE_URL}/api/authoring/sources/{doc_id}", timeout=10)
    assert d.status_code == 200

    lst2 = admin.get(f"{BASE_URL}/api/authoring/sources", timeout=10).json()
    assert not any(d["id"] == doc_id for d in lst2["items"])


def test_source_upload_learner_blocked(learner):
    r = learner.post(
        f"{BASE_URL}/api/authoring/sources",
        files={"file": ("t.txt", b"x", "text/plain")},
        data={"title": "x"}, timeout=10,
    )
    assert r.status_code == 403


def test_source_upload_rejects_no_text_or_file(admin):
    r = admin.post(f"{BASE_URL}/api/authoring/sources",
                   data={"title": "Empty"}, timeout=10)
    assert r.status_code == 400


# ── Semantic search + tutor ──────────────────────────────────────────
@pytest.fixture(scope="module")
def uploaded_doc(admin):
    """Shared fixture — uploads a small nutrition doc once per module."""
    title = f"Nutrition Fixture {uuid.uuid4().hex[:6]}"
    text = (
        "Protein is essential for muscle repair. Adults need 0.8g/kg body "
        "weight daily. Athletes need 1.2-2.0g/kg. Good protein sources include "
        "eggs, dairy, meat, and quinoa. Carbohydrates fuel exercise. Complex "
        "carbs like whole grains are preferred. Fats support hormones."
    )
    r = admin.post(
        f"{BASE_URL}/api/authoring/sources",
        data={"title": title, "text": text, "source_type": "MANUAL"},
        timeout=60,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    yield doc
    admin.delete(f"{BASE_URL}/api/authoring/sources/{doc['id']}", timeout=10)


def test_semantic_search_returns_matching_chunks(admin, uploaded_doc):
    r = admin.post(f"{BASE_URL}/api/authoring/sources/search",
                   json={"query": "how much protein for athletes"}, timeout=60)
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert hits, "expected at least one chunk"
    assert hits[0]["score"] > 0.3
    assert "protein" in hits[0]["text"].lower()


def test_tutor_answer_cites_sources(admin, uploaded_doc):
    r = admin.post(f"{BASE_URL}/api/authoring/tutor/ask",
                   json={"question": "How much protein do athletes need per day?"},
                   timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sources_used"] >= 1
    assert len(body["citations"]) >= 1
    # The answer must reference at least one source token like [S1]
    assert "[S1]" in body["answer"] or "S1" in body["answer"]
    # Cannot be the no-sources refusal
    assert body.get("no_sources") is False


def test_tutor_refuses_when_no_sources_match(admin):
    """A question completely unrelated to any uploaded doc should get the
    refusal answer, not a hallucinated response."""
    r = admin.post(f"{BASE_URL}/api/authoring/tutor/ask",
                   json={"question": "Explain quantum entanglement in stellar cosmology"},
                   timeout=60)
    body = r.json()
    # Either 0 sources (clean refusal) OR the answer explicitly says
    # "sources don't cover this"
    if body["sources_used"] == 0:
        assert "couldn't find" in body["answer"].lower() or "no sources" in body["answer"].lower()
    else:
        # If it retrieved something with a low relevance, the LLM must refuse.
        assert any(p in body["answer"].lower()
                   for p in ("don't cover", "not cover", "no information",
                             "cannot answer", "insufficient"))


def test_tutor_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/tutor/ask",
                     json={"question": "test"}, timeout=10)
    assert r.status_code == 403


# ── PII redaction toggle authorization ──────────────────────────────
def test_tutor_pii_redact_disable_admin_ok(admin, uploaded_doc):
    r = admin.post(f"{BASE_URL}/api/authoring/tutor/ask",
                   json={"question": "protein needs", "pii_redact": False},
                   timeout=60)
    assert r.status_code == 200


# ── Iter 24: Tavily deep research ─────────────────────────────────────
def test_research_start_returns_job_id_when_tavily_key_present(admin):
    """Once TAVILY_API_KEY is set in backend/.env, /research/start accepts
    the request and returns 202 with a job_id. If the key is missing this
    returns 503 with `tavily_key_missing` — kept as a skip below."""
    r = admin.post(f"{BASE_URL}/api/authoring/research/start",
                   json={"query": "music industry trends 2026", "depth": "quick"},
                   timeout=10)
    if r.status_code == 503:
        body = r.json()
        detail = body.get("detail") or body.get("error", {})
        code = detail.get("code", "") if isinstance(detail, dict) else ""
        assert code in ("tavily_key_missing", "HTTP_503")
        return
    assert r.status_code == 202
    assert isinstance(r.json().get("job_id"), int)


def test_research_start_learner_blocked(learner):
    r = learner.post(f"{BASE_URL}/api/authoring/research/start",
                     json={"query": "anything"}, timeout=10)
    assert r.status_code == 403
