"""configurable badge tiers + per-tenant smtp overrides

Revision ID: e5a721f43b18
Revises: c1f29b3e9d04
Create Date: 2026-02-08 14:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5a721f43b18"
down_revision = "c1f29b3e9d04"
branch_labels = None
depends_on = None


_DEFAULT_TIERS = [
    ("FIRST_ENROLLMENT", "First Step",    "🎯", "Enrolled in your first course",  10, 0),
    ("FIRST_COURSE",     "Graduate",      "🎓", "Completed your first course",    50, 1),
    ("EXAM_PASSER",      "Scholar",       "📚", "Passed your first exam",        100, 2),
    ("PERFECT_SCORE",    "Perfectionist", "💯", "Scored 100% on an exam",        200, 3),
    ("COURSE_MASTER",    "Course Master", "🏆", "Completed 5 courses",           500, 4),
]


def upgrade() -> None:
    op.create_table(
        "badge_tiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("emoji", sa.String(8), nullable=True, server_default="🏅"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("threshold_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "slug", name="uq_badge_tier_slug"),
    )
    op.create_index("ix_badge_tier_org_order", "badge_tiers", ["organization_id", "order_index"])

    # Per-tenant SMTP overrides
    with op.batch_alter_table("organizations") as bop:
        bop.add_column(sa.Column("smtp_host", sa.String(200), nullable=True))
        bop.add_column(sa.Column("smtp_port", sa.Integer(), nullable=True))
        bop.add_column(sa.Column("smtp_username", sa.String(200), nullable=True))
        bop.add_column(sa.Column("smtp_password_enc", sa.Text(), nullable=True))
        bop.add_column(sa.Column("smtp_from_email", sa.String(200), nullable=True))
        bop.add_column(sa.Column("smtp_from_name", sa.String(200), nullable=True))
        bop.add_column(sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()))

    # Seed default badge tiers for every existing organization so the
    # gamification service has data to consult immediately. New orgs will
    # be seeded by the InvitationService.create_academy flow.
    conn = op.get_bind()
    org_ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM organizations")).fetchall()]
    insert_sql = sa.text(
        "INSERT INTO badge_tiers (organization_id, slug, label, emoji, description, threshold_xp, order_index, is_active) "
        "VALUES (:oid, :slug, :label, :emoji, :description, :threshold_xp, :order_index, true)"
    )
    for oid in org_ids:
        for slug, label, emoji, desc, threshold, order in _DEFAULT_TIERS:
            conn.execute(insert_sql, {
                "oid": oid, "slug": slug, "label": label, "emoji": emoji,
                "description": desc, "threshold_xp": threshold, "order_index": order,
            })


def downgrade() -> None:
    with op.batch_alter_table("organizations") as bop:
        bop.drop_column("smtp_use_tls")
        bop.drop_column("smtp_from_name")
        bop.drop_column("smtp_from_email")
        bop.drop_column("smtp_password_enc")
        bop.drop_column("smtp_username")
        bop.drop_column("smtp_port")
        bop.drop_column("smtp_host")
    op.drop_index("ix_badge_tier_org_order", "badge_tiers")
    op.drop_table("badge_tiers")
