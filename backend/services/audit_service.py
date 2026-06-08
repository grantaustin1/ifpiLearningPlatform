"""Append-only audit log service.

Helper around the `audit_logs` table. Inspired by ERP360's invariants
auditor pattern (agent_007) — keep a forensic trail of who-did-what so
admin actions can be reviewed and compliance questions answered.

Usage:
    record(db, current_user, "THEME_APPLIED", target_type="organization",
           target_id=str(org.id), metadata={"preset": "conservatoire"})

Never raises — audit failures must not break the originating request.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import AuditLog

logger = logging.getLogger("ifpi.audit")


def record(
    db: Session,
    actor,
    action: str,
    *,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    try:
        ip = None
        if request is not None:
            ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                  or (request.client.host if request.client else None))
        entry = AuditLog(
            organization_id=getattr(actor, "organization_id", None),
            actor_user_id=getattr(actor, "id", None),
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            audit_metadata=metadata or {},
            ip_address=ip,
        )
        db.add(entry)
        # Caller's transaction commits this. If they roll back, the audit
        # row rolls back too — acceptable for IFPI's volume.
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("audit record failed action=%s target=%s/%s: %s",
                         action, target_type, target_id, e)
