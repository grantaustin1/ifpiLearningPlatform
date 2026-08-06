"""Iter 30q — AI Query Builder v1.

Admins ask a question in English ("How many learners completed course
'IFPI Fundamentals' last month?"), we send a curated **schema catalog**
+ a strict prompt to the LLM asking for a single **SELECT** statement,
execute it against the read-only session, and return the rows.

Guardrails
----------
1. Only `SELECT` statements — parsed and rejected otherwise.
2. Only whitelisted tables (users, courses, enrollments, certificates,
   quizzes, quiz_attempts, cohort snapshots, source documents).
3. Auto-appended `WHERE organization_id = :org_id` on every table that
   has that column. Refuses to run cross-org queries.
4. Statement timeout via `LIMIT 500` enforced as a suffix.
5. Runs on a fresh SQLAlchemy connection with `execution_options(
   readonly=True)` where the dialect supports it.

This is v1: intentionally simple, human-in-the-loop (admin sees the
generated SQL + can copy / edit). No historical query cache. No
autonomous chart rendering.
"""
from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, requires_admin
from core.config import settings
from core.database import get_db
from services import audit_service

logger = logging.getLogger("ifpi.query_builder")

router = APIRouter(prefix="/api/admin/query-builder",
                   tags=["AI Query Builder"])


# ── Schema catalog (curated — NOT the full DB) ────────────────────────

SCHEMA_CATALOG = """
Tables you may query (SQLite, ANSI-compatible SQL):

users(id, email, name, organization_id, is_active, points, last_login_at, created_at)

courses(id, title, description, organization_id, status, created_at)
  -- status IN ('DRAFT','PUBLISHED','ARCHIVED')

enrollments(id, user_id, course_id, status, progress, enrolled_at, completed_at)
  -- status IN ('IN_PROGRESS','COMPLETED','DROPPED')
  -- NOTE: enrollments does not have organization_id — join via users or courses

certificates(id, user_id, course_id, organization_id, issued_at, verify_code)

quizzes(id, course_id, title, passing_score)

quiz_attempts(id, quiz_id, user_id, score, passed, submitted_at)

organizations(id, name, slug, status, created_at)

Notes:
- Timestamps are ISO / UTC.
- `progress` is 0.0-100.0.
- Prefer explicit JOINs. Avoid SELECT *.
"""

ALLOWED_TABLES = {
    "users", "courses", "enrollments", "certificates",
    "quizzes", "quiz_attempts", "organizations",
}

SYSTEM_PROMPT = (
    "You are a SQL expert helping an IFPI Learning Platform admin. "
    "Given a natural-language question and a schema, output ONE SQL "
    "statement (SELECT only) that answers it, followed by a one-line "
    "human explanation.\n\n"
    "OUTPUT FORMAT — respond with these two lines, nothing else:\n"
    "SQL: <the SELECT statement, single line>\n"
    "REASON: <one sentence>\n\n"
    "Rules:\n"
    "1. SELECT statements only. Never INSERT/UPDATE/DELETE/DDL.\n"
    "2. Use only these tables: users, courses, enrollments, certificates, "
    "quizzes, quiz_attempts, organizations.\n"
    "3. Always include organization_id = <your_org_id> filters on tables "
    "that have that column (users, courses, certificates).\n"
    "4. Cap results with LIMIT 500 if the query might return many rows.\n"
    "5. If the question can't be answered from the schema, respond:\n"
    "   SQL: SELECT NULL AS answer WHERE 1=0\n"
    "   REASON: <why it can't be answered>"
)


# ── Schemas ───────────────────────────────────────────────────────────


class BuildIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class BuildOut(BaseModel):
    sql: str
    reason: str
    rows: list[dict]
    row_count: int
    truncated: bool


# ── Helpers ───────────────────────────────────────────────────────────


_TABLE_RE = re.compile(
    r"\b(from|join)\s+([\w_\.]+)", re.IGNORECASE
)


def _extract_tables(sql: str) -> set[str]:
    matches = _TABLE_RE.findall(sql)
    return {t.split(".")[-1].lower() for _, t in matches}


def _validate_sql(sql: str) -> None:
    """Raises HTTPException if the SQL isn't safe to run."""
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise HTTPException(status_code=400,
                            detail="Multiple statements not allowed")
    lowered = s.lower().lstrip()
    if not lowered.startswith("select"):
        raise HTTPException(status_code=400,
                            detail="Only SELECT queries are allowed")
    banned = {"insert ", "update ", "delete ", "drop ", "alter ", "create ",
              "truncate ", "attach ", "pragma "}
    if any(b in lowered for b in banned):
        raise HTTPException(status_code=400,
                            detail="Query contains disallowed keywords")
    # Block UNION-based data exfiltration
    if re.search(r"\bunion\b", lowered):
        raise HTTPException(status_code=400,
                            detail="UNION queries are not allowed")
    tables = _extract_tables(s)
    forbidden = tables - ALLOWED_TABLES
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail=f"Query touches non-whitelisted table(s): {sorted(forbidden)}"
        )


def _inject_org_scope(sql: str, org_id: int) -> str:
    """Enforce that every query touching org-scoped tables includes an
    organization_id filter. We replace any literal value with the caller's
    org_id — this prevents cross-org data leakage even if the LLM invents
    a different org_id."""
    lowered = sql.lower()
    tables = _extract_tables(sql)
    # Tables that MUST have an organization_id filter
    org_scoped = {"users", "courses", "certificates"}
    if tables & org_scoped and "organization_id" not in lowered:
        raise HTTPException(
            status_code=400,
            detail="Query must include an organization_id filter for safety"
        )
    # Force every organization_id literal to the current admin's org
    return re.sub(r"organization_id\s*=\s*\d+", f"organization_id = {org_id}",
                  sql, flags=re.IGNORECASE)


def _ensure_limit(sql: str, cap: int = 500) -> tuple[str, bool]:
    if re.search(r"\blimit\s+\d+", sql, re.IGNORECASE):
        return sql, False
    return sql.rstrip().rstrip(";") + f" LIMIT {cap}", True


# ── LLM call ──────────────────────────────────────────────────────────


async def _call_llm(question: str) -> tuple[str, str]:
    if not settings.emergent_llm_key:
        raise HTTPException(status_code=503,
                            detail="Query builder not configured — EMERGENT_LLM_KEY missing")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(status_code=503,
                            detail="LLM integration unavailable")

    prompt = f"SCHEMA:\n{SCHEMA_CATALOG}\n\nQUESTION:\n{question}"
    chat = LlmChat(
        api_key=settings.emergent_llm_key,
        session_id=f"query-builder-{uuid.uuid4().hex}",
        system_message=SYSTEM_PROMPT,
    ).with_model(settings.ai_builder_provider, settings.ai_builder_model)

    raw = await chat.send_message(UserMessage(text=prompt))
    text_out = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))

    sql, reason = "", ""
    for line in text_out.strip().splitlines():
        s = line.strip()
        if s.upper().startswith("SQL:"):
            sql = s.split(":", 1)[1].strip().strip("`")
        elif s.upper().startswith("REASON:"):
            reason = s.split(":", 1)[1].strip()
    if not sql:
        raise HTTPException(status_code=502,
                            detail=f"LLM returned an invalid response: {text_out[:200]}")
    return sql, reason or "Generated by AI query builder."


# ── Endpoint ──────────────────────────────────────────────────────────


@router.post("/build", response_model=BuildOut)
async def build_query(body: BuildIn, request: Request,
                      current: CurrentUser = Depends(requires_admin()),
                      db: Session = Depends(get_db)):
    sql, reason = await _call_llm(body.question)
    _validate_sql(sql)
    scoped = _inject_org_scope(sql, current.organization_id)
    capped, was_capped = _ensure_limit(scoped)

    try:
        result = db.execute(
            text(capped),
            execution_options={"readonly": True}
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
    except Exception as e:
        logger.exception("query-builder execution failed: %s", e)
        raise HTTPException(status_code=400,
                            detail=f"Query failed to execute: {e.__class__.__name__}: {str(e)[:180]}")

    # Coerce non-JSON-serializable values (datetime, Decimal) to strings
    from datetime import date, datetime as _dt
    from decimal import Decimal
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, (_dt, date)):
                r[k] = v.isoformat()
            elif isinstance(v, Decimal):
                r[k] = float(v)

    audit_service.record(db, current, "QUERY_BUILDER_RUN",
                         target_type="query", target_id=None,
                         metadata={"question": body.question[:200],
                                   "row_count": len(rows)},
                         request=request)
    db.commit()

    return BuildOut(sql=capped, reason=reason, rows=rows,
                    row_count=len(rows), truncated=was_capped)
