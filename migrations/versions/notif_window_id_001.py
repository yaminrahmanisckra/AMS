"""Scope student notifications to an operational window

Revision ID: notif_window_id_001
Revises: ai_phased_integrations
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'notif_window_id_001'
down_revision = 'ai_phased_integrations'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    if 'student_notification' not in tables:
        return
    cols = {c['name'] for c in inspector.get_columns('student_notification')}
    if 'window_id' not in cols:
        with op.batch_alter_table('student_notification', schema=None) as batch_op:
            batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_student_notification_window',
                'operational_window',
                ['window_id'],
                ['id'],
            )
            batch_op.create_index('ix_student_notification_window_id', ['window_id'], unique=False)

    dialect = conn.dialect.name
    if 'notice' in inspector.get_table_names():
        if dialect == 'sqlite':
            like_sql = "student_notification.link_url LIKE '%/noticeboard/' || CAST(n.id AS TEXT)"
            limit_sql = ' LIMIT 1'
        else:
            like_sql = "student_notification.link_url LIKE CONCAT('%/noticeboard/', n.id)"
            limit_sql = ''
        conn.execute(text(f'''
            UPDATE student_notification
            SET window_id = (
                SELECT n.window_id FROM notice n
                WHERE {like_sql}{limit_sql}
            )
            WHERE window_id IS NULL AND type = 'notice'
        '''))

    conn.execute(text('UPDATE student_notification SET window_id = 1 WHERE window_id IS NULL'))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'student_notification' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('student_notification')}
    if 'window_id' not in cols:
        return
    with op.batch_alter_table('student_notification', schema=None) as batch_op:
        try:
            batch_op.drop_index('ix_student_notification_window_id')
        except Exception:
            pass
        try:
            batch_op.drop_constraint('fk_student_notification_window', type_='foreignkey')
        except Exception:
            pass
        batch_op.drop_column('window_id')
