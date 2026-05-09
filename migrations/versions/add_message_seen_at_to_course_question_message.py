"""Add seen timestamps to course_question_message

Revision ID: add_message_seen_at
Revises: add_teacher_read_at
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_message_seen_at'
down_revision = 'add_teacher_read_at'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    if 'course_question_message' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('course_question_message')]
        if 'seen_by_teacher_at' not in cols:
            op.add_column('course_question_message', sa.Column('seen_by_teacher_at', sa.DateTime(), nullable=True))
        if 'seen_by_student_at' not in cols:
            op.add_column('course_question_message', sa.Column('seen_by_student_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('course_question_message', 'seen_by_student_at')
    op.drop_column('course_question_message', 'seen_by_teacher_at')
