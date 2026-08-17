"""Learner-facing qualification pathway map + admin compliance tools."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import CurrentUser, get_current_user, requires_roles
from core.database import get_db
from services.pathway_service import (
    admin_completions, grant_rpl, pathway_map, revoke_rpl,
)

pathways_router = APIRouter(prefix="/api/pathways", tags=["Pathways"])


@pathways_router.get("/map")
def get_pathway_map(db: Session = Depends(get_db),
                    current: CurrentUser = Depends(get_current_user)):
    return pathway_map(db, current)


@pathways_router.get("/admin/completions")
def get_admin_completions(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    return admin_completions(db, current.organization_id)


@pathways_router.get("/admin/completions.csv")
def export_admin_completions_csv(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    import csv
    import io
    data = admin_completions(db, current.organization_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Track", "Designation", "Learner", "Email", "Module",
                "State", "Progress %", "Qualified"])
    for t in data:
        titles = {c["course_id"]: c["title"] for c in t["courses"]}
        for row in t["learners"]:
            for cell in row["cells"]:
                w.writerow([t["title"], t["designation"], row["name"],
                            row["email"], titles.get(cell["course_id"]),
                            cell["state"], cell["progress"],
                            "yes" if row["qualified"] else "no"])
    return Response(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="qualification-compliance.csv"'})


class RplBody(BaseModel):
    user_id: int
    course_id: int


@pathways_router.post("/admin/rpl")
def post_grant_rpl(
    body: RplBody, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    return grant_rpl(db, current, body.user_id, body.course_id)


@pathways_router.delete("/admin/rpl/{user_id}/{course_id}")
def delete_rpl(
    user_id: int, course_id: int, db: Session = Depends(get_db),
    current: CurrentUser = Depends(requires_roles("ADMIN", "SUPER_ADMIN")),
):
    return revoke_rpl(db, current, user_id, course_id)
