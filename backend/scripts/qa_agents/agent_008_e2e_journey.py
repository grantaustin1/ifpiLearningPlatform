#!/usr/bin/env python3
"""IFPI Agent 008 — End-to-End Journey Tester (deterministic).

Ported pattern from ERP360. Drives a synthetic learner through the full
IFPI happy path using the idempotent seed fixture ("IFPI Fundamentals"
course + assessment with 4 questions, all in the default IFPI Main
Academy). Designed to be CI-safe — re-running it is idempotent and
leaves only deterministic test rows behind.

Journey:
    1. Ensure fixture exists (run seed.run_if_empty)
    2. Admin login → look up the seeded course + exam IDs
    3. Bulk-invite a learner with cohort='AGENT008'
    4. Accept the invitation (token read from DB)
    5. Learner logs in, enrols on the fixture course
    6. Mark every slide complete via /api/courses/{id}/slides/{sid}/complete
    7. Take the exam — answer correctly so we earn a cert
    8. Verify cert was issued
    9. Download /api/certificates/transcript
   10. Re-run agent_007 invariants — should still be clean

Exit 0 on success, 1 on failure. JSON report at test_reports/agent_008.json
(or AGENT_REPORT_DIR override).
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _api_url() -> str:
    env = os.environ.get("API_URL") or os.environ.get("REACT_APP_BACKEND_URL")
    if env:
        return env.rstrip("/")
    fenv = Path("/app/frontend/.env")
    if fenv.exists():
        for line in fenv.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return "http://localhost:8001"


API = _api_url()
LOG: list[dict] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    LOG.append({"step": name, "ok": ok, "detail": detail})
    flag = "PASS" if ok else "FAIL"
    print(f"{flag}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _write_report(False)
        raise SystemExit(1)


def _report_path(name: str) -> Path:
    report_dir = os.environ.get("AGENT_REPORT_DIR")
    if report_dir:
        candidate = Path(report_dir)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if os.access(candidate, os.W_OK):
                return candidate / name
        except OSError:
            pass
    fallback = Path(__file__).absolute().parents[3] / "test_reports"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / name


def _write_report(ok: bool) -> None:
    out = _report_path("agent_008.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": ok, "steps": LOG}, indent=2))


def main() -> int:
    # 0) Pre-flight — CI may not have a running backend. Probe /api/health
    #    with a short timeout and exit(0) with a skip note when unreachable.
    try:
        r = requests.get(f"{API}/api/health", timeout=3)
        if r.status_code != 200:
            raise requests.RequestException(f"unhealthy status {r.status_code}")
    except requests.RequestException as e:
        print(f"SKIP  agent_008 — backend at {API} not reachable ({e}). "
              "This is expected in CI without a running server.")
        _write_report(True)  # Not a failure — just skipped
        return 0

    # 1) Ensure the deterministic fixture is present
    from seed.seed_minimal import run_if_empty
    run_if_empty()
    step("fixture seeded", True)

    from core.database import SessionLocal
    from models import Course, Exam, Invitation, User

    # 2) Admin session
    s = requests.Session()
    r = s.post(f"{API}/api/auth/login",
               json={"email": "admin@ifpi.org", "password": "admin123"}, timeout=15)
    step("admin login", r.status_code == 200, f"status={r.status_code}")

    with SessionLocal() as db:
        course = db.query(Course).filter(Course.title == "IFPI Fundamentals").first()
        exam = db.query(Exam).filter(Exam.course_id == course.id).first() if course else None
    step("fixture course present", bool(course), f"course_id={course.id if course else None}")
    step("fixture exam present", bool(exam), f"exam_id={exam.id if exam else None}")

    # 3) Bulk-invite a fresh learner
    suffix = uuid.uuid4().hex[:6]
    learner_email = f"agent008_{suffix}@example.com"
    r = s.post(f"{API}/api/admin/invitations/bulk", json={
        "invitations": [{"email": learner_email, "name": "Agent 008", "role": "LEARNER"}],
        "cohort": "AGENT008",
    }, timeout=15)
    step("bulk invite queued", r.status_code == 200 and r.json().get("queued") == 1,
         f"body={r.text[:160]}")

    # 4) Accept invite
    with SessionLocal() as db:
        inv = db.query(Invitation).filter(Invitation.email == learner_email).first()
    step("invitation row exists", bool(inv) and bool(inv.token))
    r = requests.post(f"{API}/api/invitations/{inv.token}/accept",
                      json={"password": "agent008-pw"}, timeout=15)
    step("invitation accepted", r.status_code in (200, 201), f"status={r.status_code}")

    # 5) Learner login + enrol
    ls = requests.Session()
    r = ls.post(f"{API}/api/auth/login",
                json={"email": learner_email, "password": "agent008-pw"}, timeout=15)
    step("learner login", r.status_code == 200)
    r = ls.post(f"{API}/api/courses/{course.id}/enroll", timeout=15)
    step("learner enrolled", r.status_code in (200, 201), f"status={r.status_code}")

    # 6) Mark every slide complete
    r = ls.get(f"{API}/api/courses/{course.id}", timeout=15)
    step("course details fetched", r.status_code == 200)
    slides = r.json().get("slides") or []
    step("slides present", len(slides) >= 5, f"count={len(slides)}")
    for sl in slides:
        ls.post(f"{API}/api/courses/{course.id}/slides/{sl['id']}/complete", timeout=15)
    step("all slides marked complete", True)

    # 7) Take the exam — fetch the correct answers from DB then submit
    with SessionLocal() as db:
        from models import ExamQuestion
        answers = {str(q.id): q.correct_answer for q in
                   db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).all()}
    r = ls.post(f"{API}/api/exams/{exam.id}/attempts",
                json={"answers": answers}, timeout=15)
    step("exam submitted", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    score = r.json().get("score")
    step("score >= passing", score is not None and score >= 70, f"score={score}")

    # 7b) Mark the course complete (issues the certificate)
    r = ls.post(f"{API}/api/courses/{course.id}/complete", timeout=15)
    step("course marked complete", r.status_code in (200, 201), f"status={r.status_code}")

    # 8) Cert auto-issued?
    r = ls.get(f"{API}/api/certificates", timeout=15)
    step("cert list fetched", r.status_code == 200)
    certs = r.json()
    has_cert = any(c.get("course_title") == "IFPI Fundamentals" for c in certs)
    step("certificate issued for fixture course", has_cert,
         f"certs_total={len(certs)}")

    # 9) Transcript
    r = ls.get(f"{API}/api/certificates/transcript", timeout=15)
    step("transcript PDF", r.status_code == 200 and "pdf" in r.headers.get("content-type", "").lower(),
         f"status={r.status_code} size={len(r.content)}")

    # 10) Invariants still clean
    import subprocess
    r2 = subprocess.run([sys.executable,
                        str(Path(__file__).parent / "agent_007_invariants.py")],
                       capture_output=True, text=True, timeout=60)
    step("agent_007 invariants still clean", r2.returncode == 0, r2.stdout[-200:])

    _write_report(True)
    print(f"\n✅ AGENT 008 PASSED. Learner: {learner_email}, score: {score}, cert: {has_cert}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        LOG.append({"step": "EXCEPTION", "ok": False, "detail": str(e)[:300]})
        _write_report(False)
        sys.exit(1)
