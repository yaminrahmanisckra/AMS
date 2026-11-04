"""Add documents_enabled flag for admission cycles

Revision ID: add_adm_docs_enabled
Revises: add_wa_discuss_social, add_mts_witness_paper
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_adm_docs_enabled'
down_revision = ('add_wa_discuss_social', 'add_mts_witness_paper')
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'documents_enabled' in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('documents_enabled', sa.Boolean(), nullable=False, server_default='1')
        )
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.alter_column('documents_enabled', server_default=None)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    if 'documents_enabled' not in cols:
        return
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        batch_op.drop_column('documents_enabled')
