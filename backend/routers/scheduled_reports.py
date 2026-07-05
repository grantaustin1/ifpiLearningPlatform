"""Iter 30p — Custom scheduled reports.

Admins can subscribe to reports on cadence (daily/weekly/monthly). Report
generation is delegated to `services.scheduled_reports_worker` (invoked
by the existing APScheduler tick) which computes the payload, renders
HTML, and drops it into the outbox for the SMTP worker to deliver.

Endpoints
---------
- `GET  /api/admin/scheduled-reports`
- `POST /api/admin/scheduled-reports`
- `PUT  /api/admin/scheduled-reports/{id}`
- `DELETE /api/admin/scheduled-reports/{id}`
- `POST /api/admin/scheduled-reports/{id}/run-now` — force immediate run
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.database import get_db
from models import ScheduledReport
from services import audit_service

router = APIRouter(prefix="/api/admin/scheduled-reports",
                   tags=["Scheduled Reports"])


KNOWN_KINDS = frozenset({
    "members_needing_action", "cohort_progress",
    "certificate_issuance", "enrollment_summary",
})
KNOWN_CADENCE = frozenset({"daily", "weekly", "monthly"})
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class ScheduleIn(BaseModel):
    report_kind: str
    cadence: str
    recipient_emails: List[str] = Field(min_length=1, max_length=20)
    is_active: bool = True

    @field_validator("report_kind")
    @classmethod
    def _validate_kind(cls, v: str) -> str:
        if v not in KNOWN_KINDS:
            raise ValueError(f"report_kind must be one of {sorted(KNOWN_KINDS)}")
        return v

    @field_validator("cadence")
    @classmethod
    def _validate_cadence(cls, v: str) -> str:
        if v not in KNOWN_CADENCE:
            raise ValueError(f"cadence must be one of {sorted(KNOWN_CADENCE)}")
        return v

    @field_validator("recipient_emails")
    @classmethod
    def _validate_emails(cls, v: list[str]) -> list[str]:
        cleaned = [e.strip().lower() for e in v if e and e.strip()]
        bad = [e for e in cleaned if not EMAIL_RE.match(e)]
        if bad:
            raise ValueError(f"invalid email(s): {bad}")
        return cleaned


def _next_run_from(cadence: str, base: Optional[datetime] = None) -> datetime:
    base = base or datetime.utcnow()
    if cadence == "daily":
        return base + timedelta(days=1)
    if cadence == "weekly":
        return base + timedelta(days=7)
    return base + timedelta(days=30)  # monthly (approx)


def _serialize(r: ScheduledReport) -> dict:
    return {
        "id": r.id,
        "report_kind": r.report_kind,
        "cadence": r.cadence,
        "recipient_emails": r.recipient_emails or [],
        "is_active": r.is_active,
        "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
        "next_run_at": r.next_run_at.isoformat(),
        "created_at": r.created_at.isoformat(),
    }


@router.get("")
def list_scheduled(current: CurrentUser = Depends(requires_admin()),
                   db: Session = Depends(get_db)):
    rows = (db.query(ScheduledReport)
            .filter(ScheduledReport.organization_id == current.organization_id)
            .order_by(ScheduledReport.created_at.desc()).all())
    return {"items": [_serialize(r) for r in rows]}


@router.post("")
def create_scheduled(body: ScheduleIn, request: Request,
                     current: CurrentUser = Depends(requires_admin()),
                     db: Session = Depends(get_db)):
    row = ScheduledReport(
        organization_id=current.organization_id,
        created_by_user_id=current.id,
        report_kind=body.report_kind,
        cadence=body.cadence,
        recipient_emails=body.recipient_emails,
        is_active=body.is_active,
        next_run_at=_next_run_from(body.cadence),
    )
    db.add(row)
    audit_service.record(db, current, "SCHEDULED_REPORT_CREATED",
                         target_type="scheduled_report",
                         target_id=str(row.id),
                         metadata={"kind": body.report_kind,
                                   "cadence": body.cadence,
                                   "recipients": len(body.recipient_emails)},
                         request=request)
    db.commit(); db.refresh(row)
    return _serialize(row)


@router.put("/{report_id}")
def update_scheduled(report_id: int, body: ScheduleIn, request: Request,
                     current: CurrentUser = Depends(requires_admin()),
                     db: Session = Depends(get_db)):
    row = db.query(ScheduledReport).filter(
        ScheduledReport.id == report_id,
        ScheduledReport.organization_id == current.organization_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    prev_cadence = row.cadence
    row.report_kind = body.report_kind
    row.cadence = body.cadence
    row.recipient_emails = body.recipient_emails
    row.is_active = body.is_active
    # If cadence changed, reset the cursor
    if prev_cadence != body.cadence:
        row.next_run_at = _next_run_from(body.cadence)
    audit_service.record(db, current, "SCHEDULED_REPORT_UPDATED",
                         target_type="scheduled_report",
                         target_id=str(row.id), request=request)
    db.commit()
    return _serialize(row)


@router.delete("/{report_id}")
def delete_scheduled(report_id: int, request: Request,
                     current: CurrentUser = Depends(requires_admin()),
                     db: Session = Depends(get_db)):
    row = db.query(ScheduledReport).filter(
        ScheduledReport.id == report_id,
        ScheduledReport.organization_id == current.organization_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(row)
    audit_service.record(db, current, "SCHEDULED_REPORT_DELETED",
                         target_type="scheduled_report",
                         target_id=str(report_id), request=request)
    db.commit()
    return {"deleted": True}


@router.post("/{report_id}/run-now")
def run_now(report_id: int, request: Request,
            current: CurrentUser = Depends(requires_admin()),
            db: Session = Depends(get_db)):
    from services import scheduled_reports_worker

    row = db.query(ScheduledReport).filter(
        ScheduledReport.id == report_id,
        ScheduledReport.organization_id == current.organization_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    ok = scheduled_reports_worker.generate_and_enqueue(db, row)
    audit_service.record(db, current, "SCHEDULED_REPORT_MANUAL_RUN",
                         target_type="scheduled_report",
                         target_id=str(row.id),
                         metadata={"success": ok},
                         request=request)
    db.commit()
    return {"queued": ok, "report_id": row.id}
