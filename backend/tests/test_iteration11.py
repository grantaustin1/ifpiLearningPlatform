"""Iteration 11 backend tests:
- AI quiz: TRUE_FALSE / SHORT_ANSWER / MIXED question types
- AI quiz: avoid_topics LLM instruction
- PUT /exams/{id}/questions: TRUE_FALSE + SHORT_ANSWER row types
- GET /api/admin/leaderboard.csv (CSV format + cohort filter + 403 non-admin)
- GET /api/admin/audit-digest (LLM summary + deterministic fallback + 403 non-admin)
"""
import os
import subprocess
import sys
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://code-quality-check-31.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@ifpi.org", "password": "admin123"},
                      timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def learner_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "learner@ifpi.org", "password": "learner123"},
                      timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def learner_headers(learner_token):
    return {"Authorization": f"Bearer {learner_token}"}


@pytest.fixture(scope="module")
def first_course_id(admin_headers):
    r = requests.get(f"{API}/courses", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    courses = r.json()
    assert len(courses) > 0
    # Find one with slides
    for c in courses:
        cid = c["id"]
        sr = requests.get(f"{API}/courses/{cid}", headers=admin_headers, timeout=15)
        if sr.status_code == 200:
            data = sr.json()
            if data.get("slides") or data.get("module_count", 0) > 0:
                return cid
    return courses[0]["id"]


# ---------- AI quiz: question types ----------

class TestAIQuizQuestionTypes:
    def test_true_false_returns_two_options(self, admin_headers, first_course_id):
        r = requests.post(f"{API}/exams/ai-generate-questions",
                          headers=admin_headers,
                          json={"course_id": first_course_id, "num_questions": 2,
                                "question_type": "TRUE_FALSE"},
                          timeout=60)
        assert r.status_code == 200, r.text
        qs = r.json()["questions"]
        assert len(qs) >= 1
        for q in qs:
            assert q["question_type"] == "TRUE_FALSE", q
            assert q["options"] == ["True", "False"], q["options"]
            assert q["correct_answer"] in ("True", "False"), q["correct_answer"]

    def test_short_answer_returns_empty_options(self, admin_headers, first_course_id):
        r = requests.post(f"{API}/exams/ai-generate-questions",
                          headers=admin_headers,
                          json={"course_id": first_course_id, "num_questions": 2,
                                "question_type": "SHORT_ANSWER"},
                          timeout=60)
        assert r.status_code == 200, r.text
        qs = r.json()["questions"]
        assert len(qs) >= 1
        for q in qs:
            assert q["question_type"] == "SHORT_ANSWER", q
            assert q["options"] == [], q["options"]
            assert isinstance(q["correct_answer"], str) and len(q["correct_answer"]) > 0

    def test_mixed_returns_blend(self, admin_headers, first_course_id):
        r = requests.post(f"{API}/exams/ai-generate-questions",
                          headers=admin_headers,
                          json={"course_id": first_course_id, "num_questions": 5,
                                "question_type": "MIXED"},
                          timeout=90)
        assert r.status_code == 200, r.text
        qs = r.json()["questions"]
        assert len(qs) >= 3
        types = {q["question_type"] for q in qs}
        # MIXED should yield at least 2 different types
        assert len(types) >= 2, f"Expected mixed types, got {types}"

    def test_avoid_topics_honored(self, admin_headers, first_course_id):
        avoid = ["What does IFPI stand for?"]
        r = requests.post(f"{API}/exams/ai-generate-questions",
                          headers=admin_headers,
                          json={"course_id": first_course_id, "num_questions": 1,
                                "question_type": "MULTIPLE_CHOICE",
                                "avoid_topics": avoid},
                          timeout=60)
        assert r.status_code == 200, r.text
        qs = r.json()["questions"]
        assert len(qs) >= 1
        for q in qs:
            assert avoid[0].lower() not in q["question_text"].lower(), \
                f"LLM did not avoid: {q['question_text']}"


# ---------- PUT /exams/{id}/questions with TRUE_FALSE + SHORT_ANSWER ----------

class TestExamQuestionRowTypes:
    def test_put_accepts_tf_and_sa(self, admin_headers, first_course_id):
        # Create exam
        cr = requests.post(f"{API}/exams", headers=admin_headers,
                           json={"title": "TEST_iter11_types", "course_id": first_course_id,
                                 "time_limit_minutes": 10, "passing_score": 60,
                                 "max_attempts": 3, "randomize": False,
                                 "is_published": False},
                           timeout=15)
        assert cr.status_code == 200, cr.text
        exam_id = cr.json()["id"]
        try:
            body = [
                {"question_text": "IFPI is global.", "question_type": "TRUE_FALSE",
                 "options": ["True", "False"], "correct_answer": "True",
                 "explanation": "Yes", "points": 1, "order_index": 1},
                {"question_text": "What does mastering refer to?",
                 "question_type": "SHORT_ANSWER",
                 "options": [], "correct_answer": "final audio polishing",
                 "explanation": "Standard term", "points": 1, "order_index": 2},
            ]
            pr = requests.put(f"{API}/exams/{exam_id}/questions",
                              headers=admin_headers, json=body, timeout=15)
            assert pr.status_code == 200, pr.text
            rows = pr.json()
            assert len(rows) == 2
            qtypes = {r["question_type"] for r in rows}
            assert "TRUE_FALSE" in qtypes
            assert "SHORT_ANSWER" in qtypes
            # Verify persistence by GET
            gr = requests.get(f"{API}/exams/{exam_id}", headers=admin_headers, timeout=15)
            assert gr.status_code == 200
            persisted = {q["question_type"] for q in gr.json()["questions"]}
            assert "TRUE_FALSE" in persisted and "SHORT_ANSWER" in persisted
        finally:
            requests.delete(f"{API}/exams/{exam_id}", headers=admin_headers, timeout=15)


# ---------- Leaderboard CSV ----------

class TestLeaderboardCSV:
    def test_csv_format(self, admin_headers):
        r = requests.get(f"{API}/admin/leaderboard.csv", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct, ct
        body = r.text
        first_line = body.splitlines()[0]
        assert first_line == "rank,name,email,cohort,xp,badges_earned,certificates", first_line
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_csv_cohort_filter(self, admin_headers):
        # Get an existing cohort
        cr = requests.get(f"{API}/admin/cohorts", headers=admin_headers, timeout=15)
        assert cr.status_code == 200
        cohorts = cr.json()
        if not cohorts:
            pytest.skip("No cohorts exist")
        cohort = cohorts[0]["cohort"]
        r = requests.get(f"{API}/admin/leaderboard.csv?cohort={cohort}",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        cd = r.headers.get("content-disposition", "")
        assert cohort in cd, f"cohort name not in filename: {cd}"
        lines = r.text.splitlines()
        # All data rows should be in that cohort (col index 3)
        for line in lines[1:]:
            cells = line.split(",")
            if len(cells) >= 4 and cells[3]:
                assert cells[3] == cohort, line

    def test_csv_non_admin_forbidden(self, learner_headers):
        r = requests.get(f"{API}/admin/leaderboard.csv", headers=learner_headers, timeout=15)
        assert r.status_code == 403, r.status_code


# ---------- Audit digest ----------

class TestAuditDigest:
    def test_basic_response_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/audit-digest?days=14",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["days"] == 14
        assert "total_actions" in data
        assert isinstance(data["counts_by_action"], dict)
        assert isinstance(data["summary"], str) and len(data["summary"]) > 0

    def test_days_clamp_low(self, admin_headers):
        r = requests.get(f"{API}/admin/audit-digest?days=0",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["days"] == 1

    def test_days_clamp_high(self, admin_headers):
        r = requests.get(f"{API}/admin/audit-digest?days=500",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["days"] == 90

    def test_non_admin_forbidden(self, learner_headers):
        r = requests.get(f"{API}/admin/audit-digest?days=14",
                         headers=learner_headers, timeout=15)
        assert r.status_code == 403, r.status_code

    def test_deterministic_fallback_when_no_llm(self, admin_token):
        """Patch EMERGENT_LLM_KEY to empty in a subprocess call.
        Since we can't unset on the running server, we verify the deterministic
        string pattern is part of the response (the fallback uses that exact prefix)."""
        r = requests.get(f"{API}/admin/audit-digest?days=14",
                         headers={"Authorization": f"Bearer {admin_token}"},
                         timeout=30)
        assert r.status_code == 200
        s = r.json()["summary"]
        # Either LLM responded (any non-empty string) OR deterministic fallback fired
        # The deterministic pattern is: "In the last X days: N admin action(s)"
        # We just verify summary is present and non-empty; deterministic prefix is
        # exercised in unit test below.
        assert len(s) > 0

    def test_deterministic_fallback_unit(self):
        """Directly invoke the digest path with no LLM key via env patching subprocess."""
        code = (
            "import os, asyncio, sys\n"
            "os.environ.pop('EMERGENT_LLM_KEY', None)\n"
            "os.environ['EMERGENT_LLM_KEY']=''\n"
            "sys.path.insert(0, '/app/backend')\n"
            "from core.database import SessionLocal\n"
            "from auth.dependencies import CurrentUser\n"
            "from routers.iter8 import audit_digest\n"
            "from models import User\n"
            "db = SessionLocal()\n"
            "u = db.query(User).filter(User.email=='admin@ifpi.org').first()\n"
            "cu = CurrentUser(id=u.id, email=u.email, organization_id=u.organization_id, roles=[ur.role for ur in u.user_roles])\n"
            "import core.config as cfg\n"
            "cfg.settings.emergent_llm_key=''\n"
            "out = asyncio.run(audit_digest(days=14, db=db, current=cu))\n"
            "print('SUMMARY:'+out['summary'])\n"
        )
        p = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, p.stderr
        out = p.stdout
        assert "SUMMARY:" in out
        summary = out.split("SUMMARY:", 1)[1].strip()
        assert "In the last 14 days" in summary, summary
        assert "admin action" in summary, summary
