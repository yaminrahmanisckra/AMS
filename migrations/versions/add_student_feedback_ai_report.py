"""Store last AI IQAC feedback report on student_feedback_link

Revision ID: add_feedback_ai_report
Revises: answer_guideline_001
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_feedback_ai_report'
down_revision = 'answer_guideline_001'
branch_labels = None
depends_on = None


def _has_column(conn, table_name, column_name):
    inspector = inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in [column['name'] for column in inspector.get_columns(table_name)]


def upgrade():
    conn = op.get_bind()
    if not _has_column(conn, 'student_feedback_link', 'ai_report_json'):
        op.add_column('student_feedback_link', sa.Column('ai_report_json', sa.Text(), nullable=True))
    if not _has_column(conn, 'student_feedback_link', 'ai_report_generated_at'):
        op.add_column('student_feedback_link', sa.Column('ai_report_generated_at', sa.DateTime(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _has_column(conn, 'student_feedback_link', 'ai_report_generated_at'):
        op.drop_column('student_feedback_link', 'ai_report_generated_at')
    if _has_column(conn, 'student_feedback_link', 'ai_report_json'):
        op.drop_column('student_feedback_link', 'ai_report_json')
