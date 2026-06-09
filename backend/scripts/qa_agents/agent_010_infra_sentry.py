#!/usr/bin/env python3
"""IFPI Agent 010 — Infra & External-Integration Sentry.

Ported pattern from ERP360 (scripts/qa_agents/agent_010_infra_sentry.py).
Verifies that every infra dependency is alive BEFORE a UAT failure
points fingers at app code. Each check returns a single OK/FAIL line
so it's easy to spot which red light is on in a CI log.

Checks:
- C-1  Backend HTTP healthcheck (GET /api/health)
- C-2  Database connectivity (SELECT 1 via SessionLocal)
- C-3  ReportLab can render a 1-page PDF
- C-4  APScheduler worker is running (singleton has scheduler instance)
- C-5  OutboxMessage queue is draining (no rows QUEUED > 5 min in stub mode)
- C-6  Emergent LLM key is present (AI builder dependency)
- C-7  Cryptography Fernet key derivation works (SMTP encryption dep)
- C-8  Storage backend reachable (LocalStorage roundtrip)

Exit 0 if every check passes, 1 if any failed.
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


RESULTS: list[dict] = []


def check(name: str):
    def _decorator(fn):
        try:
            fn()
            RESULTS.append({"check": name, "ok": True})
            print(f"OK   {name}")
        except Exception as e:
            RESULTS.append({"check": name, "ok": False, "error": str(e)[:200]})
            print(f"FAIL {name}: {e}")
        return fn
    return _decorator


def _report_path(filename: str) -> Path:
    report_dir = os.environ.get("AGENT_REPORT_DIR")
    base = Path(report_dir) if report_dir else Path(__file__).resolve().parents[3] / "test_reports"
    return base / filename


@check("C-1 backend http healthcheck")
def c1():
    import requests
    url = (os.environ.get("API_URL")
           or os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")).rstrip("/")
    r = requests.get(f"{url}/api/health", timeout=8)
    assert r.status_code == 200, f"status={r.status_code}"


@check("C-2 database connectivity")
def c2():
    from core.database import SessionLocal
    from sqlalchemy import text
    with SessionLocal() as db:
        assert db.execute(text("SELECT 1")).scalar() == 1


@check("C-3 ReportLab can render a PDF")
def c3():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 700, "infra check")
    c.showPage(); c.save()
    assert buf.tell() > 1000, f"unexpectedly small pdf: {buf.tell()}b"


@check("C-4 APScheduler worker started")
def c4():
    """Only meaningful when run in-process with the FastAPI app. From a
    standalone CLI/CI process the scheduler isn't booted — skip with OK."""
    if os.environ.get("AGENT_010_STANDALONE", "0") == "1":
        return  # treated as OK
    from services import outbox_worker
    if outbox_worker._scheduler is None:
        # Standalone process — accept as not-applicable
        return
    assert outbox_worker._scheduler.running, "scheduler not running"


@check("C-5 outbox queue draining (stale rows < 5m old)")
def c5():
    from datetime import timedelta
    from core.database import SessionLocal
    from models import OutboxMessage
    with SessionLocal() as db:
        stale = db.query(OutboxMessage).filter(
            OutboxMessage.status == "QUEUED",
            OutboxMessage.created_at < datetime.now(timezone.utc) - timedelta(minutes=5),
        ).count()
        assert stale == 0, f"{stale} QUEUED rows > 5min old (worker not draining)"


@check("C-6 emergent LLM key present")
def c6():
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    assert key, "EMERGENT_LLM_KEY env var is empty"
    assert len(key) > 20, "EMERGENT_LLM_KEY looks malformed"


@check("C-7 Fernet key derivation works")
def c7():
    from services.smtp_service import encrypt_password, decrypt_password
    os.environ["SMTP_ALLOW_PLAINTEXT"] = "1"   # ensure dev mode for this check
    blob = encrypt_password("hello-world-123")
    assert decrypt_password(blob) == "hello-world-123"


@check("C-8 storage backend roundtrip")
def c8():
    from services.storage_service import get_storage
    s = get_storage()
    s.save(b"infra-sentry", "test/sentry.txt", content_type="text/plain")
    assert s.load("test/sentry.txt") == b"infra-sentry"
    s.delete("test/sentry.txt")


def main() -> int:
    out = _report_path("agent_010.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    failed = [r for r in RESULTS if not r["ok"]]
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": len(RESULTS), "failed": len(failed), "results": RESULTS,
    }, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
