"""Add window_id to active_semester_config for window-wise semester binding

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'active_semester_config'):
        return

    cols = {c['name'] for c in inspector.get_columns('active_semester_config')}
    if 'window_id' not in cols:
        with op.batch_alter_table('active_semester_config', schema=None) as batch_op:
            batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_active_semester_window',
                'operational_window',
                ['window_id'],
                ['id'],
            )
            batch_op.create_index('idx_active_semester_window', ['window_id', 'is_active'], unique=False)

    conn.execute(text(
        'UPDATE active_semester_config SET window_id = 1 WHERE window_id IS NULL'
    ))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'active_semester_config'):
        return

    cols = {c['name'] for c in inspector.get_columns('active_semester_config')}
    if 'window_id' in cols:
        with op.batch_alter_table('active_semester_config', schema=None) as batch_op:
            try:
                batch_op.drop_index('idx_active_semester_window')
            except Exception:
                pass
            try:
                batch_op.drop_constraint('fk_active_semester_window', type_='foreignkey')
            except Exception:
                pass
            batch_op.drop_column('window_id')
