"""IFPI bulk content migration — directory tree → DB rows.

Two entry points:
  - CLI:                 `python -m scripts.bulk_import --org-id 1 --content-dir /path`
  - In-process (router): `run_import_for_job(db, job_id, org_id, source_path, …)`
                         called from the `BackgroundTasks` queue.

Directory contract (matches the spec the academy team agreed to):

    /path/to/content/
    ├── courses/
    │   ├── foundation-personal-training/
    │   │   ├── meta.json              # optional course metadata
    │   │   ├── 01-welcome.docx
    │   │   ├── 02-concepts.pdf
    │   │   ├── 03-technique-demo.mp4
    │   │   └── 04-assessment.xlsx     # converts to Exam + questions
    │   └── advanced-nutrition/
    │       └── ...
    └── paths/
        └── certification-track.json   # ordered list of course titles

Idempotency: courses are upserted by `(organization_id, title)`. Slides are
WIPED + re-imported on each run. Exams are upserted by
`(organization_id, title, course_id)`.

Storage: media files are uploaded through the configured `storage_service`
(local / s3 / gcs — whichever STORAGE_BACKEND is set). Slides reference the
URL returned by the storage backend.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure /app/backend is importable when invoked as a CLI script.
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy.orm import Session  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from core.sanitizer import sanitize_course_html, sanitize_plain_text  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from models import (  # noqa: E402
    Course, CourseSlide, CourseStatus, Exam, ExamQuestion, ImportJob,
    LearningPath, LearningPathItem, LearningPathStatus, Organization,
    QuestionType, SlideType, User, UserRole,
)
from services.storage_service import StorageError, get_storage  # noqa: E402

logger = logging.getLogger("ifpi.bulk_import")

EXT_TO_SLIDE = {
    ".mp4": SlideType.VIDEO, ".webm": SlideType.VIDEO, ".mov": SlideType.VIDEO,
    ".avi": SlideType.VIDEO,
    ".mp3": SlideType.AUDIO, ".wav": SlideType.AUDIO, ".ogg": SlideType.AUDIO,
    ".pdf": SlideType.PDF,
    ".png": SlideType.IMAGE, ".jpg": SlideType.IMAGE, ".jpeg": SlideType.IMAGE,
    ".webp": SlideType.IMAGE, ".svg": SlideType.IMAGE, ".gif": SlideType.IMAGE,
    ".docx": SlideType.TEXT, ".md": SlideType.TEXT,
    ".html": SlideType.TEXT, ".htm": SlideType.TEXT, ".txt": SlideType.TEXT,
}

EXT_TO_MIME = {
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".pdf": "application/pdf",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif",
}

EXAM_EXTS = {".xlsx", ".xls", ".csv"}


# ───────────────────────── helpers ─────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:80] or "untitled"


def titleise(filename_stem: str) -> str:
    return sanitize_plain_text(
        filename_stem.replace("-", " ").replace("_", " ").strip().title()
    ) or "Untitled"


def _get_or_create_migration_admin(db: Session, org_id: int) -> User:
    """Ensure a deterministic migration-bot admin exists per org."""
    email = f"migration@ifpi-org-{org_id}.local"
    admin = db.query(User).filter(User.email == email).first()
    if admin:
        return admin
    admin = User(
        email=email, name="Migration Bot",
        password_hash=get_password_hash("disabled-no-login-" + os.urandom(8).hex()),
        organization_id=org_id, is_active=False,  # not for interactive login
    )
    db.add(admin)
    db.flush()
    db.add(UserRole(user_id=admin.id, role="ADMIN"))
    db.commit()
    logger.info("Created migration admin id=%s for org=%s", admin.id, org_id)
    return admin


def _extract_docx_to_html(file_path: Path) -> str:
    """Best-effort docx → HTML extraction. Preserves headings + lists."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not installed — falling back to filename")
        return f"<p>(docx content from {file_path.name} — install python-docx to extract)</p>"

    doc = Document(file_path)
    parts: list[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        style = (para.style.name or "").strip() if para.style else ""
        if style.startswith("Heading"):
            lvl = style.replace("Heading", "").strip() or "2"
            try:
                lvl_int = max(1, min(6, int(lvl)))
            except ValueError:
                lvl_int = 2
            parts.append(f"<h{lvl_int}>{text}</h{lvl_int}>")
        else:
            parts.append(f"<p>{text}</p>")
    return "\n".join(parts) or f"<p>{file_path.stem}</p>"


def _markdown_to_html(md: str) -> str:
    try:
        import markdown as _md
        return _md.markdown(md, extensions=["tables", "fenced_code"])
    except ImportError:
        # Minimal fallback — wrap each non-blank line in <p>
        return "\n".join(f"<p>{line.rstrip()}</p>"
                         for line in (md or "").splitlines() if line.strip())


def _store_media(file_path: Path, org_id: int) -> str:
    """Read a file from disk + push it through the configured storage_service.
    Returns the public URL (or local /api/uploads/files/… path)."""
    ext = file_path.suffix.lower()
    mime = EXT_TO_MIME.get(ext, "application/octet-stream")
    data = file_path.read_bytes()
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file_path.name)
    key = f"imports/{org_id}/{file_path.parent.name}/{safe_name}"
    try:
        return get_storage().save(data, key, content_type=mime)
    except StorageError as e:
        raise RuntimeError(f"Storage save failed for {file_path.name}: {e}") from e


# ───────────────────────── per-course importer ─────────────────────────
def import_course_from_directory(
    db: Session, *,
    org_id: int, admin_id: int, course_dir: Path,
    publish: bool = False,
) -> Tuple[Course, List[CourseSlide]]:
    """Import (or re-import) a single course from `course_dir`."""

    meta: dict = {}
    meta_path = course_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    title = sanitize_plain_text(
        meta.get("title") or titleise(course_dir.name)
    )
    description = sanitize_plain_text(
        meta.get("description") or f"Imported from {course_dir.name}"
    )
    category = sanitize_plain_text(meta.get("category") or "General")
    duration = int(meta.get("duration_minutes") or 0)
    price_cents = int(meta.get("price_cents") or 0)
    currency = (meta.get("currency") or "ZAR")[:3]

    status = CourseStatus.PUBLISHED if publish else CourseStatus.DRAFT

    existing = db.query(Course).filter(
        Course.organization_id == org_id, Course.title == title,
    ).first()
    if existing:
        logger.info("Updating existing course '%s' (id=%s)", title, existing.id)
        # Wipe slides — they get rebuilt below. First detach/remove rows that
        # reference the old slides (learner view history, comments, flashcards,
        # SCORM links) or SQLite raises a FOREIGN KEY IntegrityError.
        from models.ai import Flashcard
        from models.engagement import SlideView
        from models.learning import ScormPackage, SlideComment
        old_slide_ids = [sid for (sid,) in db.query(CourseSlide.id).filter(
            CourseSlide.course_id == existing.id)]
        if old_slide_ids:
            db.query(SlideView).filter(SlideView.slide_id.in_(old_slide_ids)).delete(synchronize_session=False)
            db.query(SlideComment).filter(SlideComment.slide_id.in_(old_slide_ids)).delete(synchronize_session=False)
            db.query(Flashcard).filter(Flashcard.slide_id.in_(old_slide_ids)).update({"slide_id": None}, synchronize_session=False)
            db.query(ScormPackage).filter(ScormPackage.slide_id.in_(old_slide_ids)).update({"slide_id": None}, synchronize_session=False)
        db.query(CourseSlide).filter(CourseSlide.course_id == existing.id).delete(synchronize_session=False)
        course = existing
        course.description = description
        course.category = category
        course.duration_minutes = duration
        course.status = status
        course.updated_at = _utcnow()
    else:
        course = Course(
            organization_id=org_id, title=title, description=description,
            category=category, status=status,
            duration_minutes=duration, price_cents=price_cents,
            currency=currency, created_by_id=admin_id,
        )
        db.add(course)
        db.flush()
        logger.info("Created course '%s' (id=%s)", title, course.id)

    slides: List[CourseSlide] = []
    order = 1
    # All content files, sorted alphabetically — admins use 01-, 02- prefixes.
    files = sorted([
        f for f in course_dir.iterdir()
        if f.is_file() and f.name != "meta.json" and not f.name.startswith(".")
    ], key=lambda f: f.name)

    for fp in files:
        ext = fp.suffix.lower()
        if ext in EXAM_EXTS:
            continue  # exams are processed separately
        slide_type = EXT_TO_SLIDE.get(ext)
        if slide_type is None:
            logger.warning("Skipping unsupported file: %s", fp.name)
            continue
        title_for_slide = titleise(fp.stem)

        content_html = ""
        media_url: Optional[str] = None

        if slide_type == SlideType.TEXT:
            if ext == ".docx":
                raw = _extract_docx_to_html(fp)
            elif ext == ".md":
                raw = _markdown_to_html(fp.read_text(encoding="utf-8"))
            elif ext in (".html", ".htm"):
                raw = fp.read_text(encoding="utf-8")
            else:  # .txt
                raw = "\n".join(f"<p>{ln}</p>" for ln in
                                fp.read_text(encoding="utf-8").splitlines()
                                if ln.strip())
            content_html = sanitize_course_html(raw)
        else:
            # Media slide — store the file and reference its URL.
            media_url = _store_media(fp, org_id)
            content_html = f"<p>{title_for_slide}</p>"

        slide = CourseSlide(
            course_id=course.id,
            title=title_for_slide,
            content=content_html,
            slide_type=slide_type,
            media_url=media_url,
            order_index=order,
            is_required=True,
        )
        db.add(slide)
        slides.append(slide)
        order += 1

    db.commit()
    return course, slides


def import_exam_from_spreadsheet(
    db: Session, *,
    org_id: int, admin_id: int, course_id: int, exam_file: Path,
) -> Exam:
    """Read XLSX/CSV → upsert one Exam + its ExamQuestion rows."""
    try:
        import pandas as pd
    except ImportError as e:
        raise RuntimeError("pandas not installed — needed to import quiz files") from e

    if exam_file.suffix.lower() == ".csv":
        df = pd.read_csv(exam_file)
    else:
        df = pd.read_excel(exam_file)

    exam_title = sanitize_plain_text(
        f"{exam_file.stem.replace('-', ' ').replace('_', ' ').title()} Assessment"
    )

    existing = db.query(Exam).filter(
        Exam.organization_id == org_id,
        Exam.title == exam_title,
        Exam.course_id == course_id,
    ).first()
    if existing:
        db.query(ExamQuestion).filter(ExamQuestion.exam_id == existing.id).delete()
        exam = existing
    else:
        exam = Exam(
            organization_id=org_id, title=exam_title,
            description=f"Imported from {exam_file.name}",
            course_id=course_id, time_limit_minutes=30,
            passing_score=70, max_attempts=3,
            randomize=False, is_published=False,
            created_by_id=admin_id,
        )
        db.add(exam)
        db.flush()

    order = 1
    for _, row in df.iterrows():
        q_type_str = str(row.get("question_type", "MULTIPLE_CHOICE")).upper().strip()
        try:
            q_type = QuestionType[q_type_str]
        except KeyError:
            q_type = QuestionType.MULTIPLE_CHOICE
        options = None
        opts_raw = row.get("options")
        if q_type == QuestionType.MULTIPLE_CHOICE and opts_raw is not None:
            if isinstance(opts_raw, str):
                try:
                    options = json.loads(opts_raw)
                except json.JSONDecodeError:
                    options = [s.strip() for s in opts_raw.split(",") if s.strip()]
            elif isinstance(opts_raw, list):
                options = opts_raw

        q_text = sanitize_plain_text(str(row.get("question_text") or ""))
        if not q_text:
            continue  # skip blank rows
        explanation_raw = row.get("explanation")
        explanation = (sanitize_plain_text(str(explanation_raw))
                       if explanation_raw is not None and str(explanation_raw) != "nan"
                       else None)
        points_raw = row.get("points") or 1
        try:
            points = int(points_raw)
        except (TypeError, ValueError):
            points = 1

        db.add(ExamQuestion(
            exam_id=exam.id, question_text=q_text,
            question_type=q_type, options=options,
            correct_answer=str(row.get("correct_answer") or "")[:500],
            explanation=explanation, points=points, order_index=order,
        ))
        order += 1

    db.commit()
    return exam


def import_learning_path_from_json(
    db: Session, *,
    org_id: int, admin_id: int, path_file: Path, publish: bool = False,
) -> Optional[LearningPath]:
    """Read a path JSON `{title, description, courses: [title, …], estimated_hours}`
    and create the LearningPath + ordered items."""
    with open(path_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = sanitize_plain_text(data.get("title") or path_file.stem)
    description = sanitize_plain_text(data.get("description") or "")
    estimated_hours = data.get("estimated_hours")
    course_titles = data.get("courses") or []
    course_ids: List[int] = []
    missing: List[str] = []
    for ct in course_titles:
        c = db.query(Course).filter(
            Course.organization_id == org_id,
            Course.title == sanitize_plain_text(ct),
        ).first()
        if c:
            course_ids.append(c.id)
        else:
            missing.append(ct)
    if missing:
        logger.warning("Learning path '%s' references missing courses: %s",
                       title, missing)
    if not course_ids:
        logger.warning("Skipping path '%s' — no resolvable courses", title)
        return None

    base_slug = slugify(title)
    existing = db.query(LearningPath).filter(
        LearningPath.organization_id == org_id,
        LearningPath.title == title,
    ).first()
    if existing:
        db.query(LearningPathItem).filter(
            LearningPathItem.path_id == existing.id,
        ).delete()
        path = existing
        path.description = description
        if estimated_hours is not None:
            path.estimated_hours = int(estimated_hours)
        if publish:
            path.status = LearningPathStatus.PUBLISHED
    else:
        path = LearningPath(
            organization_id=org_id, title=title, slug=base_slug,
            description=description,
            estimated_hours=int(estimated_hours) if estimated_hours else None,
            status=(LearningPathStatus.PUBLISHED if publish else LearningPathStatus.DRAFT),
            created_by_id=admin_id,
        )
        db.add(path)
        db.flush()

    for idx, cid in enumerate(course_ids, start=1):
        db.add(LearningPathItem(
            path_id=path.id, course_id=cid, order_index=idx, is_required=True,
        ))
    db.commit()
    return path


# ───────────────────────── orchestration ─────────────────────────
def _count_planned_items(content_dir: Path) -> int:
    n = 0
    courses_dir = content_dir / "courses"
    if courses_dir.exists():
        n += sum(1 for d in courses_dir.iterdir() if d.is_dir())
    paths_dir = content_dir / "paths"
    if paths_dir.exists():
        n += sum(1 for f in paths_dir.iterdir()
                 if f.is_file() and f.suffix.lower() == ".json")
    return n


def run_import_for_job(db: Session, *,
                       job_id: int, org_id: int, source_path: str,
                       publish_on_import: bool = False) -> Dict:
    """Background entry — updates the ImportJob row as it goes."""
    content_path = Path(source_path)
    job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
    if not job:
        raise RuntimeError(f"ImportJob {job_id} not found")

    job.status = "RUNNING"
    job.started_at = _utcnow()
    job.total_items = _count_planned_items(content_path)
    job.processed_items = 0
    job.failed_items = 0
    db.commit()

    admin = _get_or_create_migration_admin(db, org_id)
    results = {"courses": [], "exams": [], "paths": [], "errors": []}

    courses_dir = content_path / "courses"
    if courses_dir.exists():
        for course_dir in sorted(p for p in courses_dir.iterdir() if p.is_dir()):
            try:
                course, slides = import_course_from_directory(
                    db, org_id=org_id, admin_id=admin.id,
                    course_dir=course_dir, publish=publish_on_import,
                )
                exam_count = 0
                for f in course_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in EXAM_EXTS:
                        try:
                            import_exam_from_spreadsheet(
                                db, org_id=org_id, admin_id=admin.id,
                                course_id=course.id, exam_file=f,
                            )
                            exam_count += 1
                            results["exams"].append({
                                "course": course.title, "file": f.name,
                            })
                        except Exception as e:
                            results["errors"].append({
                                "kind": "exam", "path": str(f), "error": str(e),
                            })
                            job.failed_items += 1
                results["courses"].append({
                    "id": course.id, "title": course.title,
                    "slides": len(slides), "exams": exam_count,
                })
                job.processed_items += 1
            except Exception as e:
                logger.exception("Course import failed: %s", course_dir)
                results["errors"].append({
                    "kind": "course", "path": str(course_dir), "error": str(e),
                })
                job.failed_items += 1
            # Persist incremental progress so the UI's poll sees it
            job.results = results
            db.commit()

    paths_dir = content_path / "paths"
    if paths_dir.exists():
        for path_file in sorted(p for p in paths_dir.iterdir()
                                if p.is_file() and p.suffix.lower() == ".json"):
            try:
                p = import_learning_path_from_json(
                    db, org_id=org_id, admin_id=admin.id,
                    path_file=path_file, publish=publish_on_import,
                )
                if p:
                    results["paths"].append({"id": p.id, "title": p.title})
                job.processed_items += 1
            except Exception as e:
                logger.exception("Path import failed: %s", path_file)
                results["errors"].append({
                    "kind": "path", "path": str(path_file), "error": str(e),
                })
                job.failed_items += 1
            job.results = results
            db.commit()

    job.completed_at = _utcnow()
    job.results = results
    if job.failed_items == 0 and (job.processed_items > 0 or job.total_items == 0):
        job.status = "COMPLETED"
    elif job.processed_items > job.failed_items:
        job.status = "PARTIAL"
    else:
        job.status = "FAILED"
    db.commit()
    logger.info("Import job %s finished: %s (processed=%s, failed=%s)",
                job.id, job.status, job.processed_items, job.failed_items)
    return results


# ───────────────────────── CLI ─────────────────────────
def _cli():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Bulk-import IFPI content")
    p.add_argument("--org-id", type=int, required=True)
    p.add_argument("--content-dir", type=str, required=True)
    p.add_argument("--publish", action="store_true",
                   help="Publish courses + paths instead of leaving as DRAFT")
    args = p.parse_args()

    with SessionLocal() as db:
        # Create a synthetic ImportJob so the CLI uses the exact same code path
        org = db.query(Organization).filter(Organization.id == args.org_id).first()
        if not org:
            print(f"Organization id={args.org_id} not found", file=sys.stderr)
            sys.exit(2)
        admin = _get_or_create_migration_admin(db, args.org_id)
        job = ImportJob(
            organization_id=args.org_id, created_by_id=admin.id,
            job_type="CLI", source_path=args.content_dir, status="PENDING",
        )
        db.add(job); db.commit(); db.refresh(job)
        try:
            run_import_for_job(
                db, job_id=job.id, org_id=args.org_id,
                source_path=args.content_dir,
                publish_on_import=args.publish,
            )
        except Exception:
            traceback.print_exc()
            sys.exit(1)

        job = db.query(ImportJob).filter(ImportJob.id == job.id).first()
        print(f"\nImport {job.status}")
        print(f"  processed: {job.processed_items}")
        print(f"  failed:    {job.failed_items}")
        if job.results:
            print(f"  courses:   {len(job.results.get('courses', []))}")
            print(f"  exams:     {len(job.results.get('exams', []))}")
            print(f"  paths:     {len(job.results.get('paths', []))}")
            if job.results.get("errors"):
                print("\nErrors:")
                for err in job.results["errors"]:
                    print(f"  - [{err['kind']}] {err['path']}: {err['error']}")


if __name__ == "__main__":
    _cli()
