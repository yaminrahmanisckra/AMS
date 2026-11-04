"""Add list_kind to admission waiting/merit lists

Revision ID: add_adm_merit_kind
Revises: add_adm_waiting_lists
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'add_adm_merit_kind'
down_revision = 'add_adm_waiting_lists'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_waiting_list' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_waiting_list')}
    if 'list_kind' not in cols:
        with op.batch_alter_table('admission_waiting_list', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('list_kind', sa.String(length=20), nullable=False, server_default='waiting')
            )
        with op.batch_alter_table('admission_waiting_list', schema=None) as batch_op:
            batch_op.alter_column('list_kind', server_default=None)
    conn.execute(
        text(
            "UPDATE admission_waiting_list SET list_kind = 'waiting' "
            "WHERE list_kind IS NULL OR list_kind = ''"
        )
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_waiting_list' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_waiting_list')}
    if 'list_kind' not in cols:
        return
    with op.batch_alter_table('admission_waiting_list', schema=None) as batch_op:
        batch_op.drop_column('list_kind')
