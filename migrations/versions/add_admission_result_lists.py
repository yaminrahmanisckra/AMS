"""Add publish flags for eligible/selected admission result lists

Revision ID: add_adm_result_lists
Revises: add_adm_docs_enabled
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_adm_result_lists'
down_revision = 'add_adm_docs_enabled'
branch_labels = None
depends_on = None


def _add_bool(inspector, table, name, default='0'):
    if table not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns(table)}
    if name in cols:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(name, sa.Boolean(), nullable=False, server_default=default)
        )
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.alter_column(name, server_default=None)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    _add_bool(inspector, 'admission_cycle', 'eligible_list_published', '0')
    _add_bool(inspector, 'admission_cycle', 'selected_list_published', '0')


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_cycle' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
    with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
        if 'selected_list_published' in cols:
            batch_op.drop_column('selected_list_published')
        if 'eligible_list_published' in cols:
            batch_op.drop_column('eligible_list_published')
