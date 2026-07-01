"""Add window_id to academic calendar and self-assessment tables (Phase 2E)

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'g7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def _add_window_id(conn, inspector, table_name, fk_name):
    if not _table_exists(inspector, table_name):
        return
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    if 'window_id' in cols:
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            fk_name,
            'operational_window',
            ['window_id'],
            ['id'],
        )
    conn.execute(text(f'UPDATE {table_name} SET window_id = 1 WHERE window_id IS NULL'))


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    for table_name, fk_name in [
        ('academic_calendar_event', 'fk_academic_calendar_event_window'),
        ('psac_committee', 'fk_psac_committee_window'),
        ('survey_link', 'fk_survey_link_window'),
    ]:
        _add_window_id(conn, inspector, table_name, fk_name)

    if _table_exists(inspector, 'survey_link') and _table_exists(inspector, 'psac_committee'):
        conn.execute(text('''
            UPDATE survey_link
            SET window_id = (
                SELECT pc.window_id FROM psac_committee pc
                WHERE pc.id = survey_link.committee_id
            )
            WHERE committee_id IS NOT NULL AND (window_id IS NULL OR window_id = 1)
        '''))


def downgrade():
    pass
