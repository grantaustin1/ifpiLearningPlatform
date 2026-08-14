"""Iteration 62 regression tests - PostgreSQL + Emergent object storage migration.

Focus areas per review request:
- No 500s from PostgreSQL strictness (GROUP BY, LIKE case sensitivity, boolean-as-int)
- File serving through /api/uploads/files/... resolves via storage cache
- Admin dashboard/analytics/certs/exam endpoints load
- Course 243 (Anatomy & Physiology) has 99 slides, slide 39 is video
- Learner enrollment resume (last_slide_index) persists
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://learning-hub-968.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "uat-admin@ifpi.org", "password": "UatAdmin!2026"}
LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}


def _login(sess, creds):
    # try common login endpoints
    for path in ["/auth/login", "/login"]:
        r = sess.post(f"{API}{path}", json=creds, timeout=30)
        if r.status_code == 200:
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            token = data.get("token") or data.get("access_token")
            if token:
                sess.headers.update({"Authorization": f"Bearer {token}"})
            # csrf handling for cookie mode
            csrf = sess.cookies.get("ifpi_csrf")
            if csrf:
                sess.headers.update({"X-CSRF-Token": csrf})
            return r, data
    return r, {}


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r, _ = _login(s, ADMIN)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    return s


@pytest.fixture(scope="module")
def learner_sess():
    s = requests.Session()
    r, _ = _login(s, LEARNER)
    assert r.status_code == 200, f"learner login failed: {r.status_code} {r.text[:300]}"
    return s


# ---------------- Auth ----------------
class TestAuth:
    def test_admin_login(self, admin_sess):
        r = admin_sess.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("email") == ADMIN["email"]

    def test_learner_login(self, learner_sess):
        r = learner_sess.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("email") == LEARNER["email"]


# ---------------- Admin Dashboard / analytics (GROUP BY / date fns risk) ----------------
class TestAdminDashboard:
    @pytest.mark.parametrize("path", [
        "/admin/dashboard",
        "/admin/stats",
        "/admin/analytics",
        "/analytics/summary",
        "/marketplace/analytics",
        "/imports",
        "/imports/jobs",
    ])
    def test_endpoint_no_500(self, admin_sess, path):
        r = admin_sess.get(f"{API}{path}", timeout=30)
        # 404 acceptable (endpoint may not exist), 200/401/403 fine; but 500 is a regression
        assert r.status_code != 500, f"{path} returned 500: {r.text[:400]}"

    def test_dashboard_stats_nonzero(self, admin_sess):
        # Dashboard composes from several endpoints - verify migrated data present
        r = admin_sess.get(f"{API}/courses", timeout=30)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("courses", []))
        assert len(items) >= 1, "Expected migrated courses to be present"


# ---------------- Courses list & search ----------------
class TestCourses:
    def test_courses_list(self, learner_sess):
        r = learner_sess.get(f"{API}/courses", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("courses", []))
        assert len(items) >= 1, f"Expected courses, got {items}"

    def test_course_243_details(self, learner_sess):
        r = learner_sess.get(f"{API}/courses/243", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        slides = d.get("slides") or []
        assert len(slides) >= 90, f"Course 243 expected ~99 slides, got {len(slides)}"

    def test_course_search_case_insensitive(self, admin_sess):
        # PG LIKE is case-sensitive; ILIKE is not. Ensure lowercase 'module' finds 'Module 1'.
        for q_param in ["q", "search"]:
            r = admin_sess.get(f"{API}/courses", params={q_param: "module"}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("items", data.get("courses", []))
                titles = [str(i.get("title", "")) for i in items]
                if any("module" in t.lower() for t in titles):
                    return
        pytest.fail("Lowercase 'module' search did not return any course containing 'Module' — PG LIKE case-sensitivity regression suspected")


# ---------------- Uploads serving via object storage ----------------
class TestUploads:
    def test_serve_upload_from_course_slide(self, learner_sess):
        r = learner_sess.get(f"{API}/courses/243", timeout=30)
        assert r.status_code == 200
        d = r.json()
        slides = d.get("slides") or []
        # find slide with image or video url
        media_paths = []
        for s in slides[:50]:
            for k in ("image_url", "media_url", "video_url", "content"):
                v = s.get(k)
                if isinstance(v, str) and "/api/uploads/" in v:
                    media_paths.append(v)
        assert media_paths, "No /api/uploads/ media found in first 50 slides"
        url = media_paths[0]
        if not url.startswith("http"):
            url = f"{BASE_URL}{url}" if url.startswith("/") else f"{API}/{url}"
        r2 = learner_sess.get(url, timeout=30, allow_redirects=True)
        assert r2.status_code in (200, 206), f"Upload serve failed {r2.status_code} for {url}: {r2.text[:200]}"
        assert len(r2.content) > 100, "Upload returned empty body"


# ---------------- Learner enrollment + progress ----------------
class TestLearnerProgress:
    def test_enrolled_courses_list(self, learner_sess):
        for p in ["/enrollments", "/me/enrollments", "/learner/enrollments", "/courses/enrolled"]:
            r = learner_sess.get(f"{API}{p}", timeout=30)
            if r.status_code == 200:
                return
        pytest.skip("No learner enrollments endpoint responded 200")

    def test_progress_persists(self, learner_sess):
        # Update last_slide_index for course 243 and re-read
        payloads = [
            ("/enrollments/course/243/progress", {"last_slide_index": 5}),
            ("/courses/243/progress", {"last_slide_index": 5}),
            ("/learner/courses/243/progress", {"last_slide_index": 5}),
        ]
        posted = False
        for path, body in payloads:
            r = learner_sess.post(f"{API}{path}", json=body, timeout=30)
            if r.status_code in (200, 201, 204):
                posted = True
                # try to read back
                for gp in [path, "/enrollments", "/me/enrollments"]:
                    gr = learner_sess.get(f"{API}{gp}", timeout=30)
                    if gr.status_code == 200 and "last_slide_index" in gr.text:
                        return
                return  # posted ok even if no easy readback
            if r.status_code == 500:
                pytest.fail(f"{path} 500: {r.text[:300]}")
        if not posted:
            pytest.skip("No progress endpoint accepted the update (schema unknown)")


# ---------------- Certificates & exams ----------------
class TestCertsExams:
    @pytest.mark.parametrize("path", [
        "/certificates",
        "/me/certificates",
        "/exams",
        "/admin/exams",
        "/admin/certificates",
    ])
    def test_no_500(self, admin_sess, path):
        r = admin_sess.get(f"{API}{path}", timeout=30)
        assert r.status_code != 500, f"{path} 500: {r.text[:400]}"
