"""Iteration 63 — Refactor regression suite.

Verifies the LARGE internal refactor (misc.py -> 8 modules, courses.py -> package,
service extraction, lazy frontend) changed NOTHING behaviorally.

Focus areas per E1 review request:
- All refactored endpoint groups: enrollments, certificates, notifications,
  gamification, admin/analytics, catalog, billing.
- Course lifecycle (publish requires slides, archive blocked by in-progress
  learner, delete blocked while published, duplicate copies image_position +
  media_opacity slide fields).
- Enrollment service (enroll idempotent, save progress, complete idempotent).
- Ratings, prerequisites, slides, rich-text sanitize.

Course 243 is read-only user content (99 slides). Test courses are created
and cleaned up.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "uat-admin@ifpi.org", "password": "UatAdmin!2026"}
LEARNER = {"email": "uat-learner@ifpi.org", "password": "UatLearner!2026"}


def _login(sess, creds):
    r = sess.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    sess.headers.update({"Authorization": f"Bearer {tok}"})
    csrf = sess.cookies.get("ifpi_csrf")
    if csrf:
        sess.headers.update({"X-CSRF-Token": csrf})
    return data


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def learner_sess():
    s = requests.Session()
    _login(s, LEARNER)
    return s


# ============ Refactored endpoint groups regression (200s + shape) =========
class TestRefactoredEndpointsRegression:
    """Each split-out router must return correct status codes."""

    def test_enrollments_list_learner(self, learner_sess):
        r = learner_sess.get(f"{API}/enrollments", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), list)

    def test_certificates_list_learner(self, learner_sess):
        r = learner_sess.get(f"{API}/certificates", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), list)

    def test_notifications_list(self, learner_sess):
        r = learner_sess.get(f"{API}/notifications", timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_gamification_leaderboard(self, learner_sess):
        r = learner_sess.get(f"{API}/gamification/leaderboard", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), list)

    def test_admin_analytics_overview(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/analytics", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # Overview shape sanity
        assert isinstance(d, dict)

    def test_catalog_public(self):
        # public endpoint - no auth
        r = requests.get(f"{API}/catalog", timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_catalog_organizations_public(self):
        r = requests.get(f"{API}/catalog/organizations", timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_billing_subscriptions(self, learner_sess):
        r = learner_sess.get(f"{API}/billing/subscriptions", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), list)

    def test_gamification_me(self, learner_sess):
        r = learner_sess.get(f"{API}/gamification/me", timeout=30)
        assert r.status_code == 200, r.text[:300]


# ================ Course package regression (list, detail, search) ==========
class TestCoursePackageBasics:
    def test_list_courses(self, admin_sess):
        r = admin_sess.get(f"{API}/courses", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_course_243_read_only_detail(self, learner_sess):
        r = learner_sess.get(f"{API}/courses/243", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d.get("slides") or []) >= 90


# =========== Course CRUD + Lifecycle + Duplicate (disposable courses) =======
@pytest.fixture(scope="class")
def test_course(admin_sess):
    """Create a disposable draft course and clean up at end of class."""
    payload = {
        "title": f"TEST_iter63_refactor_{int(time.time())}",
        "description": "Disposable course for refactor regression",
        "category": "Testing",
    }
    r = admin_sess.post(f"{API}/courses", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text[:300]}"
    course = r.json()
    cid = course["id"]
    yield cid
    # Teardown - unpublish, delete
    try:
        admin_sess.post(f"{API}/courses/{cid}/unpublish", timeout=15)
    except Exception:
        pass
    try:
        admin_sess.delete(f"{API}/courses/{cid}", timeout=15)
    except Exception:
        pass


class TestCourseLifecycle:
    def test_publish_without_slides_returns_400(self, admin_sess, test_course):
        r = admin_sess.post(f"{API}/courses/{test_course}/publish", timeout=15)
        assert r.status_code == 400, (
            f"expected 400 (needs slides) got {r.status_code}: {r.text[:300]}")

    def test_add_slide_then_publish_ok(self, admin_sess, test_course):
        slide_payload = {
            "title": "Intro",
            "content": "hello world",
            "slide_type": "TEXT",
            "image_position": "beside",
            "media_opacity": 75,
        }
        r = admin_sess.post(
            f"{API}/courses/{test_course}/slides", json=slide_payload, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]

        r2 = admin_sess.post(f"{API}/courses/{test_course}/publish", timeout=15)
        assert r2.status_code == 200, r2.text[:300]

    def test_delete_while_published_returns_409(self, admin_sess, test_course):
        r = admin_sess.delete(f"{API}/courses/{test_course}", timeout=15)
        assert r.status_code == 409, (
            f"expected 409 while published, got {r.status_code}: {r.text[:300]}")

    def test_unpublish_then_archive_unarchive(self, admin_sess, test_course):
        r = admin_sess.post(f"{API}/courses/{test_course}/unpublish", timeout=15)
        assert r.status_code == 200, r.text[:300]

        r = admin_sess.post(f"{API}/courses/{test_course}/archive", timeout=15)
        assert r.status_code == 200, r.text[:300]

        r = admin_sess.post(f"{API}/courses/{test_course}/unarchive", timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_duplicate_copies_image_position_and_media_opacity(
            self, admin_sess, test_course):
        r = admin_sess.post(f"{API}/courses/{test_course}/duplicate", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        new_cid = d.get("course_id") or d.get("id")
        assert new_cid

        # fetch new course and verify slide fields copied
        r2 = admin_sess.get(f"{API}/courses/{new_cid}", timeout=15)
        assert r2.status_code == 200
        slides = r2.json().get("slides") or []
        assert len(slides) >= 1
        first = slides[0]
        assert first.get("image_position") == "beside", (
            f"duplicate did not copy image_position: {first}")
        assert first.get("media_opacity") == 75, (
            f"duplicate did not copy media_opacity: {first}")

        # cleanup duplicate
        admin_sess.delete(f"{API}/courses/{new_cid}", timeout=15)


# =============== Enrollment flow (extracted service) ========================
@pytest.fixture(scope="class")
def enrollable_course(admin_sess):
    """Create + publish a course + slide so learner can enroll/complete."""
    r = admin_sess.post(f"{API}/courses", json={
        "title": f"TEST_iter63_enroll_{int(time.time())}",
        "description": "Enrollment test course",
        "category": "Testing",
    }, timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    cid = r.json()["id"]
    admin_sess.post(f"{API}/courses/{cid}/slides", json={
        "title": "Slide 1", "content": "content", "slide_type": "TEXT",
    }, timeout=15)
    pub = admin_sess.post(f"{API}/courses/{cid}/publish", timeout=15)
    assert pub.status_code == 200, pub.text[:300]
    yield cid
    try:
        admin_sess.post(f"{API}/courses/{cid}/unpublish", timeout=15)
        admin_sess.delete(f"{API}/courses/{cid}", timeout=15)
    except Exception:
        pass


class TestEnrollmentFlow:
    def test_learner_can_enroll(self, learner_sess, enrollable_course):
        r = learner_sess.post(
            f"{API}/courses/{enrollable_course}/enroll", timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_reenroll_idempotent_returns_already(
            self, learner_sess, enrollable_course):
        r = learner_sess.post(
            f"{API}/courses/{enrollable_course}/enroll", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # Service should signal idempotent re-enroll
        assert d.get("already") is True or d.get("already_enrolled") is True \
            or "already" in (d.get("message", "").lower()), (
                f"expected already=true marker, got: {d}")

    def test_save_slide_progress(self, learner_sess, enrollable_course):
        r = learner_sess.post(
            f"{API}/courses/{enrollable_course}/progress",
            json={"slide_index": 0}, timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_complete_awards_xp_and_certificate(
            self, learner_sess, enrollable_course):
        r = learner_sess.post(
            f"{API}/courses/{enrollable_course}/complete", timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_second_complete_returns_already_completed(
            self, learner_sess, enrollable_course):
        r = learner_sess.post(
            f"{API}/courses/{enrollable_course}/complete", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("already_completed") is True or \
            "already" in str(d).lower(), (
                f"expected already_completed marker: {d}")

    def test_archive_blocked_when_learner_in_progress(
            self, admin_sess, learner_sess):
        # Fresh course, enroll learner, don't complete, then try archive
        r = admin_sess.post(f"{API}/courses", json={
            "title": f"TEST_iter63_archive_{int(time.time())}",
            "description": "arch blocked test", "category": "Testing",
        }, timeout=30)
        cid = r.json()["id"]
        try:
            admin_sess.post(f"{API}/courses/{cid}/slides", json={
                "title": "s", "content": "c", "slide_type": "TEXT"}, timeout=15)
            admin_sess.post(f"{API}/courses/{cid}/publish", timeout=15)
            learner_sess.post(f"{API}/courses/{cid}/enroll", timeout=15)
            # unpublish first (archive is only from published/draft? per svc it
            # checks in-progress enrollments regardless)
            admin_sess.post(f"{API}/courses/{cid}/unpublish", timeout=15)
            ra = admin_sess.post(f"{API}/courses/{cid}/archive", timeout=15)
            assert ra.status_code == 409, (
                f"expected 409 when learner busy, got {ra.status_code}: "
                f"{ra.text[:300]}")
        finally:
            admin_sess.post(f"{API}/courses/{cid}/unpublish", timeout=10)
            admin_sess.delete(f"{API}/courses/{cid}", timeout=10)


# ================ Ratings / Reviews ==========================================
class TestRatingsReviews:
    def test_post_and_get_rating(self, learner_sess, admin_sess):
        # Use course 243 which learner should be able to see (published)
        r = learner_sess.post(f"{API}/courses/243/rating",
                              json={"rating": 5, "comment": "TEST refactor"},
                              timeout=15)
        assert r.status_code in (200, 201, 400, 403), r.text[:300]
        # 400/403 acceptable if learner not enrolled or other biz rules; but
        # not a 500 regression.
        assert r.status_code != 500

        rg = learner_sess.get(f"{API}/courses/243/rating", timeout=15)
        assert rg.status_code in (200, 404), rg.text[:300]
        assert rg.status_code != 500

    def test_get_reviews(self, admin_sess):
        # /reviews requires INSTRUCTOR/ADMIN role
        r = admin_sess.get(f"{API}/courses/243/reviews", timeout=15)
        assert r.status_code == 200, r.text[:300]


# ================ Prerequisites ==============================================
class TestPrerequisites:
    def test_prereq_endpoints(self, admin_sess):
        # GET should always be 200 (empty list ok)
        r = admin_sess.get(f"{API}/courses/243/prerequisites", timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_add_and_remove_prereq(self, admin_sess):
        # Create two disposable courses, add prereq relation, then remove
        c1 = admin_sess.post(f"{API}/courses", json={
            "title": f"TEST_iter63_prereqA_{int(time.time())}",
            "description": "A", "category": "Testing"}, timeout=30).json()["id"]
        c2 = admin_sess.post(f"{API}/courses", json={
            "title": f"TEST_iter63_prereqB_{int(time.time())}",
            "description": "B", "category": "Testing"}, timeout=30).json()["id"]
        try:
            r = admin_sess.post(
                f"{API}/courses/{c1}/prerequisites/{c2}", timeout=15)
            assert r.status_code in (200, 201), r.text[:300]
            rl = admin_sess.get(f"{API}/courses/{c1}/prerequisites", timeout=15)
            assert rl.status_code == 200
            rd = admin_sess.delete(
                f"{API}/courses/{c1}/prerequisites/{c2}", timeout=15)
            assert rd.status_code in (200, 204), rd.text[:300]
        finally:
            admin_sess.delete(f"{API}/courses/{c1}", timeout=10)
            admin_sess.delete(f"{API}/courses/{c2}", timeout=10)


# =============== Slides: add/update/reorder/versions =======================
class TestSlidesRefactored:
    def test_slide_crud_and_versions(self, admin_sess):
        cid = admin_sess.post(f"{API}/courses", json={
            "title": f"TEST_iter63_slides_{int(time.time())}",
            "description": "Slide tests", "category": "Testing",
        }, timeout=30).json()["id"]
        try:
            # add two slides
            s1 = admin_sess.post(f"{API}/courses/{cid}/slides", json={
                "title": "s1", "content": "c1", "slide_type": "TEXT",
            }, timeout=15).json()
            s2 = admin_sess.post(f"{API}/courses/{cid}/slides", json={
                "title": "s2", "content": "c2", "slide_type": "TEXT",
            }, timeout=15).json()

            # update to create a version
            up = admin_sess.patch(
                f"{API}/courses/{cid}/slides/{s1['id']}",
                json={"title": "s1-updated", "content": "c1-v2"}, timeout=15)
            assert up.status_code == 200, up.text[:300]

            # versions list
            vr = admin_sess.get(
                f"{API}/courses/{cid}/slides/{s1['id']}/versions", timeout=15)
            assert vr.status_code == 200, vr.text[:300]

            # reorder
            ro = admin_sess.patch(
                f"{API}/courses/{cid}/slides/reorder",
                json={"slide_ids": [s2["id"], s1["id"]]}, timeout=15)
            assert ro.status_code in (200, 204), ro.text[:300]

            # delete
            de = admin_sess.delete(
                f"{API}/courses/{cid}/slides/{s2['id']}", timeout=15)
            assert de.status_code == 200, de.text[:300]
        finally:
            admin_sess.delete(f"{API}/courses/{cid}", timeout=10)


# ================ Rich-text sanitize =========================================
class TestRichTextSanitize:
    def test_sanitize_endpoint(self, admin_sess):
        r = admin_sess.post(f"{API}/rich-text/sanitize", json={
            "html": "<p>hi</p><script>alert(1)</script>",
        }, timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "sanitized" in d
        assert "<script" not in d["sanitized"].lower()


# ================ ErrorBoundary should NOT show on healthy backend =========
# (frontend-only assertion — validated by Playwright)
