"""Add written/viva/total marks on admission candidates

Revision ID: add_adm_cand_marks
Revises: add_adm_merit_kind
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_adm_cand_marks'
down_revision = 'add_adm_merit_kind'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_candidate' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_candidate')}
    with op.batch_alter_table('admission_candidate', schema=None) as batch_op:
        if 'written_marks' not in cols:
            batch_op.add_column(sa.Column('written_marks', sa.Float(), nullable=True))
        if 'viva_marks' not in cols:
            batch_op.add_column(sa.Column('viva_marks', sa.Float(), nullable=True))
        if 'total_marks' not in cols:
            batch_op.add_column(sa.Column('total_marks', sa.Float(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_candidate' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_candidate')}
    with op.batch_alter_table('admission_candidate', schema=None) as batch_op:
        if 'total_marks' in cols:
            batch_op.drop_column('total_marks')
        if 'viva_marks' in cols:
            batch_op.drop_column('viva_marks')
        if 'written_marks' in cols:
            batch_op.drop_column('written_marks')
