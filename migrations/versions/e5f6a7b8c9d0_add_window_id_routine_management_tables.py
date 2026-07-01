"""Add window_id to routine management tables (Phase 2C)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-25 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
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


def _replace_unique(conn, table_name, old_names, new_name, columns):
    if conn.dialect.name == 'sqlite':
        return
    for old in old_names:
        try:
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.drop_constraint(old, type_='unique')
        except Exception:
            pass
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.create_unique_constraint(new_name, columns)
    except Exception:
        pass


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    for table_name, fk_name in [
        ('saved_routine', 'fk_saved_routine_window'),
        ('routine', 'fk_routine_window'),
        ('routine_time_slot', 'fk_routine_time_slot_window'),
        ('assigned_course', 'fk_assigned_course_window'),
    ]:
        _add_window_id(conn, inspector, table_name, fk_name)

    if _table_exists(inspector, 'saved_routine'):
        _replace_unique(
            conn,
            'saved_routine',
            ['saved_routine_year_key', 'uq_saved_routine_window_year', 'year'],
            'uq_saved_routine_window_year',
            ['window_id', 'year'],
        )

    if _table_exists(inspector, 'assigned_course'):
        _replace_unique(
            conn,
            'assigned_course',
            ['_teacher_course_part_uc', '_teacher_course_part_window_uc'],
            '_teacher_course_part_window_uc',
            ['window_id', 'teacher_id', 'course_id', 'part'],
        )


def downgrade():
    pass
