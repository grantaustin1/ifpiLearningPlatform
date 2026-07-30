"""custom theme presets table

Revision ID: 1a2b3c4d5e6f
Revises: a5b6c7d8e9f0
Create Date: 2026-07-30
"""
import sqlalchemy as sa
from alembic import op

revision = "1a2b3c4d5e6f"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "custom_theme_presets" in insp.get_table_names():
        return  # idempotent — dev create_all may have made it already
    op.create_table(
        "custom_theme_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("primary_color", sa.String(16), nullable=False,
                  server_default="#6366f1"),
        sa.Column("cert_accent_color", sa.String(16), nullable=False,
                  server_default="#6366f1"),
        sa.Column("cert_signature_text_suggestion", sa.String(200)),
        sa.Column("cert_footer_text_suggestion", sa.Text()),
        sa.Column("cover_color", sa.String(40), server_default="bg-indigo-500"),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("organization_id", "slug",
                            name="uq_custom_theme_org_slug"),
    )


def downgrade() -> None:
    op.drop_table("custom_theme_presets")
