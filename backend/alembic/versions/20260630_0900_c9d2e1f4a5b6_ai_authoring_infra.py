"""AI authoring shared infra — SourceDocument, SourceChunk, AIJob, AIUsageLedger
+ organizations.ai_monthly_budget_cents (Iter 22).

Revision ID: c9d2e1f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-06-30 09:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d2e1f4a5b6"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def _has(insp, table: str) -> bool:
    return table in insp.get_table_names()


def _has_column(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Add AI monthly budget column to organizations (idempotent)
    if _has(insp, "organizations") and not _has_column(insp, "organizations", "ai_monthly_budget_cents"):
        with op.batch_alter_table("organizations") as bop:
            bop.add_column(sa.Column(
                "ai_monthly_budget_cents", sa.Integer(), nullable=False,
                server_default=sa.text("20000"),
            ))

    if not _has(insp, "source_documents"):
        op.create_table(
            "source_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("course_id", sa.Integer(),
                      sa.ForeignKey("courses.id"), nullable=True, index=True),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("original_url", sa.String(800)),
            sa.Column("storage_key", sa.String(400)),
            sa.Column("extracted_text", sa.Text()),
            sa.Column("metadata_json", sa.JSON()),
            sa.Column("chunk_count", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("embedded_at", sa.DateTime()),
            sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )

    if not _has(insp, "source_chunks"):
        op.create_table(
            "source_chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(),
                      sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("embedding", sa.JSON()),
            sa.Column("token_count", sa.Integer()),
        )
        op.create_index("ix_chunk_doc_ord", "source_chunks",
                        ["document_id", "chunk_index"])

    if not _has(insp, "ai_jobs"):
        op.create_table(
            "ai_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("job_type", sa.String(40), nullable=False, index=True),
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="PENDING", index=True),
            sa.Column("input_json", sa.JSON()),
            sa.Column("output_json", sa.JSON()),
            sa.Column("artefact_url", sa.String(600)),
            sa.Column("cost_cents", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("error_log", sa.Text()),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_ai_jobs_org_status", "ai_jobs",
                        ["organization_id", "status"])

    if not _has(insp, "ai_usage_ledger"):
        op.create_table(
            "ai_usage_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(),
                      sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("ai_jobs.id"), nullable=True),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("model", sa.String(60)),
            sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0")),
            sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0")),
            sa.Column("cost_cents", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("billing_month", sa.String(7), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_ai_usage_org_month", "ai_usage_ledger",
                        ["organization_id", "billing_month"])


def downgrade() -> None:
    op.drop_table("ai_usage_ledger")
    op.drop_table("ai_jobs")
    op.drop_table("source_chunks")
    op.drop_table("source_documents")
    with op.batch_alter_table("organizations") as bop:
        bop.drop_column("ai_monthly_budget_cents")
