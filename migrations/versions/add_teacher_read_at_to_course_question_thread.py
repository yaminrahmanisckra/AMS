"""Add teacher_read_at to course_question_thread for question notifications

Revision ID: add_teacher_read_at
Revises: add_course_question_tables
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_teacher_read_at'
down_revision = 'add_course_question_tables'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    if 'course_question_thread' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('course_question_thread')]
        if 'teacher_read_at' not in cols:
            op.add_column('course_question_thread', sa.Column('teacher_read_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('course_question_thread', 'teacher_read_at')
