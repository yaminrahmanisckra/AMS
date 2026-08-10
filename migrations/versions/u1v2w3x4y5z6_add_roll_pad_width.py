"""Add roll_pad_width for zero-padded admission roll numbers

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'u1v2w3x4y5z6'
down_revision = 't0u1v2w3x4y5'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'roll_pad_width' in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('roll_pad_width', sa.Integer(), nullable=False, server_default='0')
        )
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.alter_column('roll_pad_width', server_default=None)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'roll_pad_width' not in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.drop_column('roll_pad_width')
