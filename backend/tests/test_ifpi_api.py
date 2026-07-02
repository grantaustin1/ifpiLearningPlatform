"""IFPI LMS — Backend API regression tests."""
import os
import uuid
import time
import importlib.util

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend env if env-var missing in pytest shell
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests",
                allow_module_level=True)

ADMIN_CREDS = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER_CREDS = {"email": "learner@ifpi.org", "password": "learner123"}
HAS_EMERGENT_LLM_KEY = bool(os.environ.get("EMERGENT_LLM_KEY", "").strip())


# ── Fixtures ────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="session")
def learner_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=LEARNER_CREDS, timeout=15)
    assert r.status_code == 200, f"Learner login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ── Health & basics ─────────────────────────────────────────────────
class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_root(self):
        r = requests.get(f"{BASE_URL}/api", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "sso_enabled" in body and "billing_live_mode" in body


# ── Auth ────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_admin(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == ADMIN_CREDS["email"]
        assert "ADMIN" in body["user"]["roles"] or "SUPER_ADMIN" in body["user"]["roles"]

    def test_login_learner(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=LEARNER_CREDS, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == LEARNER_CREDS["email"]
        assert "LEARNER" in body["user"]["roles"]

    def test_login_bad_credentials(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@ifpi.org", "password": "wrong"}, timeout=10)
        assert r.status_code in (400, 401)

    def test_register_creates_learner_only(self):
        """Security: self-registration must create LEARNER, never ADMIN."""
        email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/register",
                          json={"email": email, "password": "Passw0rd!", "name": "Test User"},
                          timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["email"].lower() == email.lower()
        assert body["user"]["roles"] == ["LEARNER"], f"Expected LEARNER only, got {body['user']['roles']}"

    def test_me_endpoint(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == LEARNER_CREDS["email"]

    def test_sso_disabled(self):
        r = requests.post(f"{BASE_URL}/api/auth/sso-exchange",
                          json={"erp_token": "fake"}, timeout=10)
        assert r.status_code == 503


# ── Public catalog (no auth) ────────────────────────────────────────
class TestCatalog:
    def test_catalog_public(self):
        r = requests.get(f"{BASE_URL}/api/catalog", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "courses" in data
        # seeded "IFPI Fundamentals" should be there
        titles = [c["title"] for c in data["courses"]]
        assert any("IFPI" in t or "Fundamentals" in t for t in titles), f"Seeded course missing. Got: {titles}"


# ── Courses (role-gated) ────────────────────────────────────────────
class TestCourses:
    def test_list_courses_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/courses", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_courses_learner(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/courses", timeout=10)
        assert r.status_code == 200

    def test_create_course_unauthenticated_blocked(self):
        r = requests.post(f"{BASE_URL}/api/courses",
                          json={"title": "Should fail"}, timeout=10)
        assert r.status_code == 401

    def test_create_course_learner_forbidden(self, learner_session):
        r = learner_session.post(f"{BASE_URL}/api/courses",
                                 json={"title": "Learner cannot create"}, timeout=10)
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text}"

    def test_create_update_get_delete_course_admin(self, admin_session):
        title = f"TEST_Course_{uuid.uuid4().hex[:6]}"
        r = admin_session.post(f"{BASE_URL}/api/courses",
                               json={"title": title, "description": "test desc"}, timeout=15)
        assert r.status_code == 200, r.text
        course = r.json()
        cid = course["id"]
        assert course["title"] == title

        # GET back to verify persistence
        rg = admin_session.get(f"{BASE_URL}/api/courses/{cid}", timeout=10)
        assert rg.status_code == 200
        assert rg.json()["title"] == title

        # PATCH (publish for downstream tests)
        rp = admin_session.patch(f"{BASE_URL}/api/courses/{cid}",
                                 json={"title": title + "_upd", "status": "PUBLISHED"}, timeout=10)
        assert rp.status_code == 200
        assert rp.json()["title"].endswith("_upd")
        assert rp.json()["status"] == "PUBLISHED"

        # Add a slide
        rs = admin_session.post(f"{BASE_URL}/api/courses/{cid}/slides",
                                json={"title": "Slide 1", "content": "Hello", "slide_type": "TEXT"},
                                timeout=10)
        assert rs.status_code == 200

        # DELETE
        rd = admin_session.delete(f"{BASE_URL}/api/courses/{cid}", timeout=10)
        assert rd.status_code == 200

        # Verify gone
        rg2 = admin_session.get(f"{BASE_URL}/api/courses/{cid}", timeout=10)
        assert rg2.status_code == 404

    def test_enrol_free_course_learner(self, learner_session):
        """Seeded course id=1 is free; enrol should NOT return 402."""
        prereqs = learner_session.get(f"{BASE_URL}/api/courses/1/prerequisites", timeout=10)
        assert prereqs.status_code == 200, prereqs.text
        for prereq in prereqs.json() or []:
            enroll = learner_session.post(f"{BASE_URL}/api/courses/{prereq['course_id']}/enroll", timeout=10)
            assert enroll.status_code == 200, f"Prereq enroll failed: {enroll.status_code} {enroll.text}"
            complete = learner_session.post(f"{BASE_URL}/api/courses/{prereq['course_id']}/complete", timeout=10)
            assert complete.status_code == 200, f"Prereq completion failed: {complete.status_code} {complete.text}"
        r = learner_session.post(f"{BASE_URL}/api/courses/1/enroll", timeout=10)
        assert r.status_code == 200, f"Free course enrol failed: {r.status_code} {r.text}"
        assert r.json().get("ok") is True


# ── Exams ───────────────────────────────────────────────────────────
class TestExams:
    def test_list_exams_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/exams", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_exam_1_learner(self, learner_session):
        """Seeded exam id=1 with 4 questions."""
        r = learner_session.get(f"{BASE_URL}/api/exams/1", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("question_count", len(data.get("questions", []))) >= 4
        # Correct answers must be stripped for learner
        for q in data.get("questions", []):
            assert q.get("correct_answer") == ""

    def test_take_exam_and_grading(self, learner_session, admin_session):
        """Submit answers to exam 1 and verify grading + TF normalization."""
        # Admin fetches detail to see correct answers
        ra = admin_session.get(f"{BASE_URL}/api/exams/1", timeout=10)
        assert ra.status_code == 200
        qs = ra.json()["questions"]
        # Build a perfect-answer submission as dict {qid: answer}
        answers = {str(q["id"]): q.get("correct_answer", "") for q in qs}
        rs = learner_session.post(f"{BASE_URL}/api/exams/1/attempts",
                                  json={"answers": answers}, timeout=15)
        if rs.status_code == 400 and "Maximum attempts reached" in rs.text:
            pytest.skip("Seeded learner has exhausted exam attempts in this environment")
        assert rs.status_code == 200, rs.text
        result = rs.json()
        assert "score" in result
        # All correct → should pass and earn XP
        assert result["score"] >= 75, f"Expected high score for correct answers; got {result}"


# ── Course player → certificate ─────────────────────────────────────
class TestLearnerFlow:
    def test_complete_course_and_get_certificate(self, learner_session):
        # complete seeded course 1
        rc = learner_session.post(f"{BASE_URL}/api/courses/1/complete", timeout=10)
        assert rc.status_code == 200, rc.text
        # certificate list
        rcert = learner_session.get(f"{BASE_URL}/api/certificates", timeout=10)
        assert rcert.status_code == 200
        certs = rcert.json()
        assert any(c.get("course_title") for c in certs), "No cert returned after completion"
        code = certs[0]["code"]
        # public verify
        rv = requests.get(f"{BASE_URL}/api/certificates/verify/{code}", timeout=10)
        assert rv.status_code == 200
        body = rv.json()
        assert body["valid"] is True
        assert body["recipient_name"]


# ── Leaderboard / gamification ──────────────────────────────────────
class TestLeaderboard:
    def test_leaderboard(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/gamification/leaderboard", timeout=10)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 1

    def test_my_gamification(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/gamification/me", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "points" in body and "rank" in body


# ── Admin analytics & users ─────────────────────────────────────────
class TestAdmin:
    def test_analytics(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/analytics", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "monthly_enrollments" in data
        assert isinstance(data["monthly_enrollments"], list)
        assert len(data["monthly_enrollments"]) == 6
        assert data["total_courses"] >= 1

    def test_analytics_learner_forbidden(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/admin/analytics", timeout=10)
        assert r.status_code == 403

    def test_admin_users(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/users", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Billing (stub) ──────────────────────────────────────────────────
class TestBilling:
    def test_my_subscriptions(self, learner_session):
        r = learner_session.get(f"{BASE_URL}/api/billing/subscriptions", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_subscribe_stub(self, learner_session, admin_session):
        """Create a paid course and subscribe as learner in STUB mode."""
        title = f"TEST_Paid_{uuid.uuid4().hex[:6]}"
        rc = admin_session.post(f"{BASE_URL}/api/courses",
                                json={"title": title, "price_cents": 9900,
                                      "currency": "USD", "status": "PUBLISHED"},
                                timeout=10)
        assert rc.status_code == 200
        cid = rc.json()["id"]
        rs = learner_session.post(f"{BASE_URL}/api/billing/subscribe",
                                  json={"course_id": cid}, timeout=10)
        assert rs.status_code == 200, rs.text
        body = rs.json()
        assert body.get("is_stub") is True
        assert body.get("status") == "ACTIVE"
        # cleanup
        admin_session.delete(f"{BASE_URL}/api/courses/{cid}", timeout=10)


# ── AI builder ──────────────────────────────────────────────────────
@pytest.mark.skipif(not os.environ.get("EMERGENT_LLM_KEY"), reason="EMERGENT_LLM_KEY not set")
class TestAIBuilder:
    @pytest.mark.skipif(not HAS_EMERGENT_LLM_KEY, reason="EMERGENT_LLM_KEY is required for AI builder tests")
    def test_ai_course_builder(self, admin_session):
        if not AI_INTEGRATION_AVAILABLE:
            pytest.skip("AI integration unavailable (EMERGENT_LLM_KEY and package required)")
        payload = {"topic": "Python basics", "num_slides": 3,
                   "include_quiz": True, "num_questions": 2}
        t0 = time.time()
        r = admin_session.post(f"{BASE_URL}/api/ai/course-builder",
                               json=payload, timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"AI builder failed in {elapsed:.1f}s: {r.status_code} {r.text}"
        body = r.json()
        assert "slides" in body and len(body["slides"]) >= 1
        if payload["include_quiz"]:
            assert "questions" in body
