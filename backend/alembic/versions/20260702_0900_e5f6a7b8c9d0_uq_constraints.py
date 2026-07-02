"""Belt-and-braces DB constraints (Iter 25b P1 backlog).

Adds:
- `courses` UNIQUE (organization_id, title) — mirrors app-side check in
  routers/courses.py::create_course so future migrations / raw imports
  can't sneak duplicates in.
- `course_slides` UNIQUE (course_id, order_index) — the slide-reorder
  drag-and-drop UI already keeps this true, but an out-of-band bulk
  import could otherwise clobber it.

Both are wrapped in existence checks — safe to re-run on a partially
migrated DB.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-02 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def _existing_constraints(insp, table: str) -> set[str]:
    return {u["name"] for u in insp.get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    # ── Iter 26a: narration columns on course_slides ─────────────────
    if "course_slides" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("course_slides")}
        with op.batch_alter_table("course_slides") as bop:
            if "narration_url" not in cols:
                bop.add_column(sa.Column("narration_url", sa.String(500), nullable=True))
            if "narration_voice" not in cols:
                bop.add_column(sa.Column("narration_voice", sa.String(30), nullable=True))

    if "courses" in insp.get_table_names():
        existing = _existing_constraints(insp, "courses")
        if "uq_courses_org_title" not in existing:
            # Deduplicate first — keep lowest id for each (org, title) pair
            bind.exec_driver_sql("""
                DELETE FROM courses
                WHERE id NOT IN (
                    SELECT MIN(id) FROM courses
                    GROUP BY organization_id, title
                )
            """)
            if dialect == "sqlite":
                # SQLite ALTER TABLE limitations — use batch mode
                with op.batch_alter_table("courses") as bop:
                    bop.create_unique_constraint(
                        "uq_courses_org_title", ["organization_id", "title"])
            else:
                op.create_unique_constraint(
                    "uq_courses_org_title", "courses",
                    ["organization_id", "title"])

    if "course_slides" in insp.get_table_names():
        existing = _existing_constraints(insp, "course_slides")
        if "uq_course_slides_order" not in existing:
            # Deduplicate: keep lowest id per (course_id, order_index)
            bind.exec_driver_sql("""
                DELETE FROM course_slides
                WHERE id NOT IN (
                    SELECT MIN(id) FROM course_slides
                    GROUP BY course_id, order_index
                )
            """)
            if dialect == "sqlite":
                with op.batch_alter_table("course_slides") as bop:
                    bop.create_unique_constraint(
                        "uq_course_slides_order", ["course_id", "order_index"])
            else:
                op.create_unique_constraint(
                    "uq_course_slides_order", "course_slides",
                    ["course_id", "order_index"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("course_slides") as bop:
            bop.drop_constraint("uq_course_slides_order", type_="unique")
            bop.drop_column("narration_voice")
            bop.drop_column("narration_url")
        with op.batch_alter_table("courses") as bop:
            bop.drop_constraint("uq_courses_org_title", type_="unique")
    else:
        op.drop_constraint("uq_course_slides_order", "course_slides", type_="unique")
        op.drop_column("course_slides", "narration_voice")
        op.drop_column("course_slides", "narration_url")
        op.drop_constraint("uq_courses_org_title", "courses", type_="unique")
