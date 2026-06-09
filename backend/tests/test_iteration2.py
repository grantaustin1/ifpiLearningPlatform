"""IFPI LMS Iteration 2 — Tests for publish workflow, learning paths, PDF certificates,
Person row auto-creation, and Alembic schema verification."""
import os
import sqlite3
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_CREDS = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER_CREDS = {"email": "learner@ifpi.org", "password": "learner123"}
database_url = os.environ.get("DATABASE_URL", "sqlite:///./ifpi_lms.db")
if database_url.startswith("sqlite:///"):
    DB_PATH = os.path.abspath(database_url.replace("sqlite:///", "", 1))
else:
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ifpi_lms.db"))


# ── Fixtures ────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS, timeout=15)
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture(scope="session")
def learner_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=LEARNER_CREDS, timeout=15)
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


# ── Alembic / Schema ────────────────────────────────────────────────
class TestAlembicSchema:
    REQUIRED = {
        "organizations", "users", "persons", "learning_paths",
        "learning_path_items", "learning_path_enrollments",
        "course_prerequisites", "course_slides", "exams",
        "exam_questions", "exam_attempts", "certificates",
        "alembic_version", "courses", "enrollments",
    }

    def test_all_tables_present(self):
        c = sqlite3.connect(DB_PATH)
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        c.close()
        missing = self.REQUIRED - names
        assert not missing, f"Missing tables: {missing}"

    def test_alembic_version_marked(self):
        c = sqlite3.connect(DB_PATH)
        rows = c.execute("SELECT version_num FROM alembic_version").fetchall()
        c.close()
        assert rows, "alembic_version table is empty"

    def test_seed_users_have_person_rows(self):
        c = sqlite3.connect(DB_PATH)
        for email in ("admin@ifpi.org", "learner@ifpi.org"):
            row = c.execute(
                "SELECT p.id, p.lifecycle_stage FROM users u JOIN persons p ON p.user_id=u.id WHERE u.email=?",
                (email,),
            ).fetchone()
            assert row is not None, f"No Person row for {email}"
            assert row[1] in ("LEARNER", "PROSPECT", "ALUMNI"), f"Bad lifecycle_stage for {email}: {row[1]}"
        c.close()


# ── Person auto-create on register ──────────────────────────────────
class TestPersonAutoCreate:
    def test_register_creates_person(self):
        email = f"test_person_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "Passw0rd!", "name": "Person Test"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        user_id = r.json()["user"]["id"]
        # Query DB to confirm linked Person row exists & lifecycle is LEARNER
        c = sqlite3.connect(DB_PATH)
        row = c.execute(
            "SELECT id, lifecycle_stage, email FROM persons WHERE user_id=?",
            (user_id,),
        ).fetchone()
        c.close()
        assert row is not None, f"No Person row created for user_id={user_id}"
        assert row[1] == "LEARNER", f"Expected LEARNER, got {row[1]}"
        assert row[2].lower() == email.lower()


# ── Course publish / unpublish workflow ─────────────────────────────
class TestPublishWorkflow:
    def test_publish_empty_course_rejected(self, admin_session):
        title = f"TEST_Empty_{uuid.uuid4().hex[:6]}"
        rc = admin_session.post(f"{BASE_URL}/api/courses", json={"title": title}, timeout=10)
        assert rc.status_code == 200
        cid = rc.json()["id"]
        rp = admin_session.post(f"{BASE_URL}/api/courses/{cid}/publish", timeout=10)
        assert rp.status_code == 400, rp.text
        assert "slide" in rp.text.lower()
        admin_session.delete(f"{BASE_URL}/api/courses/{cid}")

    def test_publish_with_slide_then_unpublish(self, admin_session):
        title = f"TEST_Pub_{uuid.uuid4().hex[:6]}"
        rc = admin_session.post(f"{BASE_URL}/api/courses", json={"title": title}, timeout=10)
        cid = rc.json()["id"]
        admin_session.post(
            f"{BASE_URL}/api/courses/{cid}/slides",
            json={"title": "S1", "content": "x", "slide_type": "TEXT"},
            timeout=10,
        )
        rp = admin_session.post(f"{BASE_URL}/api/courses/{cid}/publish", timeout=10)
        assert rp.status_code == 200, rp.text
        assert rp.json()["status"] == "PUBLISHED"
        # Unpublish
        ru = admin_session.post(f"{BASE_URL}/api/courses/{cid}/unpublish", timeout=10)
        assert ru.status_code == 200, ru.text
        assert ru.json()["status"] == "DRAFT"
        admin_session.delete(f"{BASE_URL}/api/courses/{cid}")


# ── PDF certificate download ────────────────────────────────────────
class TestCertificatePDF:
    @pytest.fixture(scope="class")
    def cert_id(self, learner_session):
        # Ensure learner has at least one cert via complete on seeded course 1
        learner_session.post(f"{BASE_URL}/api/courses/1/complete", timeout=10)
        r = learner_session.get(f"{BASE_URL}/api/certificates", timeout=10)
        assert r.status_code == 200
        certs = r.json()
        assert certs, "Learner has no certificates"
        return certs[0]["id"]

    def test_owner_pdf_download(self, learner_session, cert_id):
        r = learner_session.get(f"{BASE_URL}/api/certificates/{cert_id}/pdf", timeout=15)
        assert r.status_code == 200, r.text
        assert "application/pdf" in r.headers.get("content-type", "").lower()
        assert r.content[:4] == b"%PDF", "Response body does not start with %PDF"

    def test_admin_can_download_any_pdf(self, admin_session, cert_id):
        r = admin_session.get(f"{BASE_URL}/api/certificates/{cert_id}/pdf", timeout=15)
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"

    def test_other_user_forbidden(self, cert_id):
        # Create a fresh user and try to access learner's cert
        email = f"intruder_{uuid.uuid4().hex[:6]}@example.com"
        rr = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "Passw0rd!", "name": "Intruder"},
            timeout=15,
        )
        assert rr.status_code == 200
        token = rr.json()["access_token"]
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}"})
        r = s.get(f"{BASE_URL}/api/certificates/{cert_id}/pdf", timeout=15)
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text[:200]}"


# ── Learning Paths ──────────────────────────────────────────────────
class TestLearningPaths:
    def test_full_crud_and_enroll_flow(self, admin_session, learner_session):
        # Create a path
        title = f"TEST_Path_{uuid.uuid4().hex[:6]}"
        rc = admin_session.post(
            f"{BASE_URL}/api/learning-paths",
            json={"title": title, "description": "desc", "cover_color": "#aabbcc"},
            timeout=10,
        )
        assert rc.status_code == 200, rc.text
        pid = rc.json()["id"]
        assert rc.json()["status"] in ("DRAFT", "draft")

        # Update via PATCH
        rp = admin_session.patch(
            f"{BASE_URL}/api/learning-paths/{pid}",
            json={"title": title + "_upd", "total_hours": 5, "price_cents": 0},
            timeout=10,
        )
        assert rp.status_code == 200
        assert rp.json()["title"].endswith("_upd")

        # Publishing path with 0 items → 400
        rpub = admin_session.post(f"{BASE_URL}/api/learning-paths/{pid}/publish", timeout=10)
        assert rpub.status_code == 400, rpub.text
        assert "course" in rpub.text.lower()

        # Add seeded course id=1
        ra = admin_session.post(
            f"{BASE_URL}/api/learning-paths/{pid}/items",
            json={"course_id": 1},
            timeout=10,
        )
        assert ra.status_code == 200, ra.text
        # Duplicate add must fail
        ra2 = admin_session.post(
            f"{BASE_URL}/api/learning-paths/{pid}/items",
            json={"course_id": 1},
            timeout=10,
        )
        assert ra2.status_code == 400

        # Publish now succeeds
        rpub2 = admin_session.post(f"{BASE_URL}/api/learning-paths/{pid}/publish", timeout=10)
        assert rpub2.status_code == 200, rpub2.text
        assert rpub2.json()["status"] == "PUBLISHED"

        # Learner sees only PUBLISHED paths
        rl = learner_session.get(f"{BASE_URL}/api/learning-paths", timeout=10)
        assert rl.status_code == 200
        learner_paths = rl.json()
        assert any(p["id"] == pid for p in learner_paths), "Published path not visible to learner"

        # Learner enrols
        re1 = learner_session.post(f"{BASE_URL}/api/learning-paths/{pid}/enroll", timeout=10)
        assert re1.status_code == 200, re1.text
        # Second call is idempotent
        re2 = learner_session.post(f"{BASE_URL}/api/learning-paths/{pid}/enroll", timeout=10)
        assert re2.status_code == 200
        assert re2.json().get("already") is True

        # Remove item
        rd = admin_session.delete(f"{BASE_URL}/api/learning-paths/{pid}/items/1", timeout=10)
        assert rd.status_code == 200

        # Delete path
        rdel = admin_session.delete(f"{BASE_URL}/api/learning-paths/{pid}", timeout=10)
        assert rdel.status_code == 200

    def test_learner_sees_only_published(self, admin_session, learner_session):
        # Create a DRAFT-only path and verify learner cannot see
        title = f"TEST_Draft_{uuid.uuid4().hex[:6]}"
        rc = admin_session.post(
            f"{BASE_URL}/api/learning-paths",
            json={"title": title},
            timeout=10,
        )
        pid = rc.json()["id"]
        rl = learner_session.get(f"{BASE_URL}/api/learning-paths", timeout=10)
        ids = [p["id"] for p in rl.json()]
        assert pid not in ids, "Learner can see DRAFT path"
        # Admin sees all
        ra = admin_session.get(f"{BASE_URL}/api/learning-paths", timeout=10)
        admin_ids = [p["id"] for p in ra.json()]
        assert pid in admin_ids
        admin_session.delete(f"{BASE_URL}/api/learning-paths/{pid}")
