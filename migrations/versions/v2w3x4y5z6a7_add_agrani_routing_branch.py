"""Add Agrani Bank routing number and branch to admission cycles

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'v2w3x4y5z6a7'
down_revision = 'u1v2w3x4y5z6'
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
        inspector, 'admission_cycle', 'agrani_routing_number',
        sa.Column('agrani_routing_number', sa.String(length=40), nullable=True),
    )
    _add_col(
        inspector, 'admission_cycle', 'agrani_branch',
        sa.Column('agrani_branch', sa.String(length=120), nullable=True),
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('admission_cycle')}
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        for col in ('agrani_branch', 'agrani_routing_number'):
            if col in existing:
                batch_op.drop_column(col)
