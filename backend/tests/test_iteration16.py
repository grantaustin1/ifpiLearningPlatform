"""Iteration 16 — Bulk content migration: extended uploads, sanitizer,
ImportJob tracking, and the bulk_import script.

Most tests run in-process so we exercise the real SQLAlchemy models + storage
abstraction. Two HTTP tests guard the public endpoints (upload + jobs).
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN = {"email": "admin@ifpi.org", "password": "admin123"}
LEARNER = {"email": "learner@ifpi.org", "password": "learner123"}


@pytest.fixture(scope="module")
def admin_token():
    time.sleep(1.5)
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def learner_token():
    time.sleep(1.5)
    r = requests.post(f"{BASE_URL}/api/auth/login", json=LEARNER, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def tmp_content_tree():
    """Build a tiny content tree on a tmp dir; cleaned up automatically."""
    with tempfile.TemporaryDirectory() as root:
        rp = Path(root)
        courses = rp / "courses"
        courses.mkdir()

        # Course 1 — docx (simulated as .txt because we don't ship a fixture docx)
        c1 = courses / "foundation-training"
        c1.mkdir()
        (c1 / "meta.json").write_text(json.dumps({
            "title": "Foundation Training",
            "description": "Intro to the platform",
            "category": "Fitness",
            "duration_minutes": 45,
        }))
        (c1 / "01-welcome.txt").write_text("Welcome line 1\nWelcome line 2")
        (c1 / "02-overview.md").write_text("# Overview\n\nKey points listed below.")
        (c1 / "03-html-with-xss.html").write_text(
            "<p>Hello</p><script>alert('xss')</script><h2>Section</h2>"
        )
        # Tiny PDF body — not a real PDF, just any binary for the storage path
        (c1 / "04-manual.pdf").write_bytes(b"%PDF-1.4 fake bytes for test")
        # Tiny "video" file — exercises media upload branch
        (c1 / "05-demo.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom..fake mp4..")

        # Course 2 — minimal (just a single text slide)
        c2 = courses / "starter-pack"
        c2.mkdir()
        (c2 / "01-intro.txt").write_text("Starter pack intro.")

        # Learning path that references the two courses
        paths = rp / "paths"
        paths.mkdir()
        (paths / "track-a.json").write_text(json.dumps({
            "title": "Career Track A",
            "description": "Two-course track for testing",
            "courses": ["Foundation Training", "Starter Pack"],
            "estimated_hours": 5,
        }))

        yield rp


# ─── Sanitizer unit tests ──────────────────────────────────────────────
class TestSanitizer:
    def test_strips_script_tag(self):
        from core.sanitizer import sanitize_course_html
        out = sanitize_course_html("<p>Hi</p><script>window.evil=1</script>")
        # The actual security defence: the <script> TAG is gone so the JS
        # cannot execute. Inner text may survive as plain text, which is safe.
        assert "<script" not in out
        assert "</script>" not in out
        assert "<p>Hi</p>" in out

    def test_keeps_safe_html(self):
        from core.sanitizer import sanitize_course_html
        out = sanitize_course_html("<h2>T</h2><p>x</p><ul><li>a</li></ul>")
        for tok in ("<h2>", "<p>", "<ul>", "<li>"):
            assert tok in out

    def test_strips_onclick_handler(self):
        from core.sanitizer import sanitize_course_html
        out = sanitize_course_html('<p onclick="evil()">hi</p>')
        assert "onclick" not in out
        assert ">hi</p>" in out

    def test_strips_javascript_url(self):
        from core.sanitizer import sanitize_course_html
        out = sanitize_course_html('<a href="javascript:alert(1)">x</a>')
        assert "javascript:" not in out

    def test_plain_text_strips_all_tags(self):
        from core.sanitizer import sanitize_plain_text
        assert sanitize_plain_text("<h1>Hello</h1>") == "Hello"
        assert sanitize_plain_text(None) == ""


# ─── Bulk import end-to-end (in-process) ───────────────────────────────
class TestBulkImport:
    def test_full_run_creates_courses_slides_path(self, tmp_content_tree):
        from core.database import SessionLocal
        from models import (Course, CourseSlide, ImportJob, LearningPath,
                            LearningPathItem, Organization)
        from scripts.bulk_import import run_import_for_job

        with SessionLocal() as db:
            org = db.query(Organization).order_by(Organization.id.asc()).first()
            assert org
            # Create a job to host the import
            from models import User
            admin = db.query(User).filter(User.email == "admin@ifpi.org").first()
            job = ImportJob(
                organization_id=org.id, created_by_id=admin.id,
                job_type="TEST", source_path=str(tmp_content_tree),
                status="PENDING",
            )
            db.add(job); db.commit(); db.refresh(job)
            jid = job.id

            # Execute
            run_import_for_job(db, job_id=jid, org_id=org.id,
                               source_path=str(tmp_content_tree),
                               publish_on_import=False)

            job = db.query(ImportJob).filter(ImportJob.id == jid).first()
            assert job.status in ("COMPLETED", "PARTIAL"), \
                f"unexpected status {job.status}; errors={job.results.get('errors') if job.results else None}"
            assert job.processed_items >= 3  # 2 courses + 1 path

            # Courses present
            foundation = db.query(Course).filter(
                Course.organization_id == org.id,
                Course.title == "Foundation Training",
            ).first()
            assert foundation is not None
            assert foundation.category == "Fitness"
            assert foundation.duration_minutes == 45

            # Slides — should have 5 (txt + md + html + pdf + mp4)
            slides = db.query(CourseSlide).filter(
                CourseSlide.course_id == foundation.id,
            ).order_by(CourseSlide.order_index).all()
            assert len(slides) == 5, f"got {len(slides)}: {[s.title for s in slides]}"

            # XSS sanitised in the HTML slide
            html_slide = next(s for s in slides if "Xss" in s.title)
            assert "<script" not in (html_slide.content or "")

            # Media slide has a media_url set
            mp4_slide = next(s for s in slides if s.title.lower().endswith("demo"))
            assert mp4_slide.media_url
            assert mp4_slide.slide_type.value == "VIDEO"

            # Learning path created with 2 items in order
            path = db.query(LearningPath).filter(
                LearningPath.organization_id == org.id,
                LearningPath.title == "Career Track A",
            ).first()
            assert path is not None
            items = db.query(LearningPathItem).filter(
                LearningPathItem.path_id == path.id,
            ).order_by(LearningPathItem.order_index).all()
            assert len(items) == 2

    def test_idempotent_rerun(self, tmp_content_tree):
        """Running the same import twice should leave one row per (org,title)."""
        from core.database import SessionLocal
        from models import (Course, CourseSlide, ImportJob, Organization, User)
        from scripts.bulk_import import run_import_for_job

        with SessionLocal() as db:
            org = db.query(Organization).order_by(Organization.id.asc()).first()
            admin = db.query(User).filter(User.email == "admin@ifpi.org").first()

            def _one_run():
                job = ImportJob(
                    organization_id=org.id, created_by_id=admin.id,
                    job_type="TEST_IDEMP", source_path=str(tmp_content_tree),
                    status="PENDING",
                )
                db.add(job); db.commit(); db.refresh(job)
                run_import_for_job(db, job_id=job.id, org_id=org.id,
                                   source_path=str(tmp_content_tree))
                return job.id

            _one_run()
            count_after_first = db.query(Course).filter(
                Course.organization_id == org.id,
                Course.title == "Foundation Training",
            ).count()
            slides_after_first = db.query(CourseSlide).join(Course).filter(
                Course.organization_id == org.id,
                Course.title == "Foundation Training",
            ).count()

            _one_run()
            count_after_second = db.query(Course).filter(
                Course.organization_id == org.id,
                Course.title == "Foundation Training",
            ).count()
            slides_after_second = db.query(CourseSlide).join(Course).filter(
                Course.organization_id == org.id,
                Course.title == "Foundation Training",
            ).count()

            assert count_after_first == 1
            assert count_after_second == 1  # no duplicate course
            assert slides_after_second == slides_after_first  # slides re-imported, not duplicated


# ─── Extended media upload HTTP tests ──────────────────────────────────
class TestExtendedUpload:
    def test_pdf_upload_accepted(self, admin_token):
        files = {"file": ("manual.pdf", b"%PDF-1.4 test", "application/pdf")}
        r = requests.post(
            f"{BASE_URL}/api/uploads/media",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["category"] == "pdf"
        assert body["url"]

    def test_video_upload_accepted(self, admin_token):
        files = {"file": ("demo.mp4", b"\x00fake mp4 bytes\x00" * 10, "video/mp4")}
        r = requests.post(
            f"{BASE_URL}/api/uploads/media",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["category"] == "video"

    def test_unsupported_mime_rejected(self, admin_token):
        files = {"file": ("evil.exe", b"MZ\x00", "application/x-msdownload")}
        r = requests.post(
            f"{BASE_URL}/api/uploads/media",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_learner_forbidden(self, learner_token):
        files = {"file": ("manual.pdf", b"%PDF-1.4 test", "application/pdf")}
        r = requests.post(
            f"{BASE_URL}/api/uploads/media",
            files=files,
            headers={"Authorization": f"Bearer {learner_token}"},
            timeout=15,
        )
        assert r.status_code in (401, 403), r.text


# ─── ImportJob HTTP endpoints ──────────────────────────────────────────
class TestImportJobsHTTP:
    def test_learner_forbidden(self, learner_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/imports",
            headers={"Authorization": f"Bearer {learner_token}"},
            timeout=10,
        )
        assert r.status_code in (401, 403)

    def test_run_with_missing_path_returns_400(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/imports/run",
            json={"source_path": "/nope/this/does/not/exist"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 400, r.text

    def test_run_with_real_path_kicks_off_job(self, admin_token, tmp_content_tree):
        # Trigger
        r = requests.post(
            f"{BASE_URL}/api/admin/imports/run",
            json={"source_path": str(tmp_content_tree), "job_type": "HTTP_TEST",
                  "publish_on_import": False},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 202, r.text
        job = r.json()
        assert job["status"] in ("PENDING", "RUNNING", "COMPLETED", "PARTIAL")
        jid = job["id"]

        # Poll status — should complete within ~10s
        for _ in range(40):
            time.sleep(0.5)
            r2 = requests.get(
                f"{BASE_URL}/api/admin/imports/{jid}",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )
            assert r2.status_code == 200
            s = r2.json()["status"]
            if s in ("COMPLETED", "PARTIAL", "FAILED"):
                break
        assert s in ("COMPLETED", "PARTIAL"), f"Final status: {s}"

        # List shows it
        rL = requests.get(
            f"{BASE_URL}/api/admin/imports",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert rL.status_code == 200
        ids = [it["id"] for it in rL.json()["items"]]
        assert jid in ids
