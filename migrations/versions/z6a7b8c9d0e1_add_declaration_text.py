"""Add admission cycle declaration_text column

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'z6a7b8c9d0e1'
down_revision = 'y5z6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'declaration_text' in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.add_column(sa.Column('declaration_text', sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'declaration_text' not in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.drop_column('declaration_text')
