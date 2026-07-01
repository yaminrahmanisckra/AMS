"""Add window_id to result_session for window-scoped result management

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-25 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'result_session'):
        return

    cols = {c['name'] for c in inspector.get_columns('result_session')}
    if 'window_id' not in cols:
        with op.batch_alter_table('result_session', schema=None) as batch_op:
            batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_result_session_window',
                'operational_window',
                ['window_id'],
                ['id'],
            )
            batch_op.create_index('idx_result_session_window', ['window_id'], unique=False)

    conn.execute(text('UPDATE result_session SET window_id = 1 WHERE window_id IS NULL'))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'result_session'):
        return

    cols = {c['name'] for c in inspector.get_columns('result_session')}
    if 'window_id' in cols:
        with op.batch_alter_table('result_session', schema=None) as batch_op:
            try:
                batch_op.drop_index('idx_result_session_window')
            except Exception:
                pass
            try:
                batch_op.drop_constraint('fk_result_session_window', type_='foreignkey')
            except Exception:
                pass
            batch_op.drop_column('window_id')
