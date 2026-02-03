"""Add course Q&A tables

Revision ID: add_course_question_tables
Revises: d2428cff2ac8
Create Date: 2026-01-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_course_question_tables'
down_revision = 'd2428cff2ac8'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'course_question_thread' not in existing_tables:
        op.create_table(
            'course_question_thread',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=50), nullable=False),
            sa.Column('student_name', sa.String(length=100), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('subject', sa.String(length=200), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['class_session.id']),
            sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_course_question_thread_session_id', 'course_question_thread', ['session_id'])
        op.create_index('ix_course_question_thread_student_id', 'course_question_thread', ['student_id'])
        op.create_index('ix_course_question_thread_teacher_id', 'course_question_thread', ['teacher_id'])
        op.create_index('ix_course_question_thread_created_at', 'course_question_thread', ['created_at'])

    if 'course_question_message' not in existing_tables:
        op.create_table(
            'course_question_message',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('thread_id', sa.Integer(), nullable=False),
            sa.Column('sender_role', sa.String(length=20), nullable=False),
            sa.Column('sender_user_id', sa.Integer(), nullable=True),
            sa.Column('body', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['thread_id'], ['course_question_thread.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_course_question_message_thread_id', 'course_question_message', ['thread_id'])
        op.create_index('ix_course_question_message_created_at', 'course_question_message', ['created_at'])

    if 'course_question_attachment' not in existing_tables:
        op.create_table(
            'course_question_attachment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('message_id', sa.Integer(), nullable=False),
            sa.Column('file_name', sa.String(length=255), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=True),
            sa.Column('file_type', sa.String(length=100), nullable=True),
            sa.Column('uploaded_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['message_id'], ['course_question_message.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_course_question_attachment_message_id', 'course_question_attachment', ['message_id'])


def downgrade():
    op.drop_index('ix_course_question_attachment_message_id', table_name='course_question_attachment')
    op.drop_table('course_question_attachment')
    op.drop_index('ix_course_question_message_created_at', table_name='course_question_message')
    op.drop_index('ix_course_question_message_thread_id', table_name='course_question_message')
    op.drop_table('course_question_message')
    op.drop_index('ix_course_question_thread_created_at', table_name='course_question_thread')
    op.drop_index('ix_course_question_thread_teacher_id', table_name='course_question_thread')
    op.drop_index('ix_course_question_thread_student_id', table_name='course_question_thread')
    op.drop_index('ix_course_question_thread_session_id', table_name='course_question_thread')
    op.drop_table('course_question_thread')
