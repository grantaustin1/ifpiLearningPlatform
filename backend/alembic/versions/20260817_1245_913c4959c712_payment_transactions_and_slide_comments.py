"""Add payment_transactions and slide_comments tables

These tables were created by Base.metadata.create_all() in production
but never had Alembic migrations.  This revision makes the schema
declarative and drift-gate clean.  Both CREATE TABLE calls are
idempotent (table-existence check first) so the migration is safe to
run against a DB that already has the tables.

Revision ID: 913c4959c712
Revises: 663872c56b9b
Create Date: 2026-08-17 12:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '913c4959c712'
down_revision = '663872c56b9b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = set(inspector.get_table_names())

    if 'payment_transactions' not in existing:
        op.create_table(
            'payment_transactions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('product_type', sa.String(length=32), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('amount_cents', sa.Integer(), nullable=False),
            sa.Column('currency', sa.String(length=8), nullable=False),
            sa.Column('stripe_session_id', sa.String(length=200), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('payment_status', sa.String(length=32), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_payment_transactions_organization_id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_payment_transactions_user_id'),
            sa.PrimaryKeyConstraint('id', name='pk_payment_transactions')
        )
        with op.batch_alter_table('payment_transactions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_payment_transactions_organization_id'), ['organization_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_payment_transactions_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_payment_transactions_stripe_session_id'), ['stripe_session_id'], unique=True)
            batch_op.create_index(batch_op.f('ix_payment_transactions_user_id'), ['user_id'], unique=False)
            batch_op.create_index('ix_payment_txn_org_user', ['organization_id', 'user_id'], unique=False)

    if 'slide_comments' not in existing:
        op.create_table(
            'slide_comments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('slide_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['parent_id'], ['slide_comments.id'], name='fk_slide_comments_parent_id'),
            sa.ForeignKeyConstraint(['slide_id'], ['course_slides.id'], name='fk_slide_comments_slide_id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_slide_comments_user_id'),
            sa.PrimaryKeyConstraint('id', name='pk_slide_comments')
        )
        with op.batch_alter_table('slide_comments', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_slide_comments_parent_id'), ['parent_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_slide_comments_slide_id'), ['slide_id'], unique=False)
            batch_op.create_index('ix_comments_slide_created', ['slide_id', 'created_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = set(inspector.get_table_names())

    if 'slide_comments' in existing:
        with op.batch_alter_table('slide_comments', schema=None) as batch_op:
            batch_op.drop_index('ix_comments_slide_created')
            batch_op.drop_index(batch_op.f('ix_slide_comments_slide_id'))
            batch_op.drop_index(batch_op.f('ix_slide_comments_parent_id'))
        op.drop_table('slide_comments')

    if 'payment_transactions' in existing:
        with op.batch_alter_table('payment_transactions', schema=None) as batch_op:
            batch_op.drop_index('ix_payment_txn_org_user')
            batch_op.drop_index(batch_op.f('ix_payment_transactions_user_id'))
            batch_op.drop_index(batch_op.f('ix_payment_transactions_stripe_session_id'))
            batch_op.drop_index(batch_op.f('ix_payment_transactions_status'))
            batch_op.drop_index(batch_op.f('ix_payment_transactions_organization_id'))
        op.drop_table('payment_transactions')
