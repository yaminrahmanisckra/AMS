"""Add is_enabled flag for admission cycles

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'is_enabled' in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1')
        )
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.alter_column('is_enabled', server_default=None)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'is_enabled' not in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.drop_column('is_enabled')
