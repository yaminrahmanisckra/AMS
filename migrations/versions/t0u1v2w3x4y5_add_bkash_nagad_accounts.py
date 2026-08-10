"""Add bKash and Nagad account numbers for admission cycles

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 't0u1v2w3x4y5'
down_revision = 's9t0u1v2w3x4'
branch_labels = None
depends_on = None


def _add_col(inspector, table, name, column):
    if table not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns(table)}
    if name in cols:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.add_column(column)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    _add_col(
        inspector, 'admission_cycle', 'bkash_account_number',
        sa.Column('bkash_account_number', sa.String(length=50), nullable=True),
    )
    _add_col(
        inspector, 'admission_cycle', 'nagad_account_number',
        sa.Column('nagad_account_number', sa.String(length=50), nullable=True),
    )
    # Widen enabled-methods string if still short
    if 'admission_cycle' in inspector.get_table_names():
        cols = {c['name']: c for c in inspector.get_columns('admission_cycle')}
        col = cols.get('payment_methods_enabled')
        if col is not None:
            with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
                batch_op.alter_column(
                    'payment_methods_enabled',
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=120),
                    existing_nullable=False,
                )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('admission_cycle')}
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        for col in ('nagad_account_number', 'bkash_account_number'):
            if col in existing:
                batch_op.drop_column(col)
