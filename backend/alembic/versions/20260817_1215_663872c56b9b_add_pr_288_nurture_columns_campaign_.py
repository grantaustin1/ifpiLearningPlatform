"""Add PR #288 nurture columns, campaign_links, pathway columns

Revision ID: 663872c56b9b
Revises: a0d1e2f3a4b5
Create Date: 2026-08-17 12:15:33.410596
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '663872c56b9b'
down_revision: Union[str, None] = 'a0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('campaign_links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=40), nullable=False),
    sa.Column('auto_enroll_course_id', sa.Integer(), nullable=True),
    sa.Column('signup_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['auto_enroll_course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaign_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaign_links_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_links_slug'), ['slug'], unique=True)

    op.create_table('campaign_signups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('campaign_link_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('utm_source', sa.String(length=120), nullable=True),
    sa.Column('utm_medium', sa.String(length=120), nullable=True),
    sa.Column('utm_campaign', sa.String(length=120), nullable=True),
    sa.Column('nudged_at', sa.DateTime(), nullable=True),
    sa.Column('second_nudged_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['campaign_link_id'], ['campaign_links.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaign_signups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaign_signups_campaign_link_id'), ['campaign_link_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_signups_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('certificates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('learning_path_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_certificates_learning_path_id'), ['learning_path_id'], unique=False)
        batch_op.create_foreign_key('fk_certificates_learning_path_id', 'learning_paths', ['learning_path_id'], ['id'])

    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('via_rpl', sa.Boolean(), server_default='0', nullable=False))

    with op.batch_alter_table('learning_paths', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metadata_json', sa.Text(), nullable=True))

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nurture_enabled', sa.Boolean(), server_default='0', nullable=True))
        batch_op.add_column(sa.Column('nurture_days', sa.Integer(), server_default='3', nullable=True))
        batch_op.add_column(sa.Column('nurture_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('nurture_second_enabled', sa.Boolean(), server_default='0', nullable=True))
        batch_op.add_column(sa.Column('nurture_second_days', sa.Integer(), server_default='7', nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('nurture_second_days')
        batch_op.drop_column('nurture_second_enabled')
        batch_op.drop_column('nurture_message')
        batch_op.drop_column('nurture_days')
        batch_op.drop_column('nurture_enabled')

    with op.batch_alter_table('learning_paths', schema=None) as batch_op:
        batch_op.drop_column('metadata_json')

    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.drop_column('via_rpl')

    with op.batch_alter_table('certificates', schema=None) as batch_op:
        batch_op.drop_constraint('fk_certificates_learning_path_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_certificates_learning_path_id'))
        batch_op.drop_column('learning_path_id')

    with op.batch_alter_table('campaign_signups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaign_signups_user_id'))
        batch_op.drop_index(batch_op.f('ix_campaign_signups_campaign_link_id'))

    op.drop_table('campaign_signups')

    with op.batch_alter_table('campaign_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaign_links_slug'))
        batch_op.drop_index(batch_op.f('ix_campaign_links_organization_id'))

    op.drop_table('campaign_links')
