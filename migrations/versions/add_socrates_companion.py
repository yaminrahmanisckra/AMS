"""Socrates AI debate companion tables

Revision ID: add_socrates_companion
Revises: add_feedback_ai_report
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_socrates_companion'
down_revision = 'add_feedback_ai_report'
branch_labels = None
depends_on = None


def _table_names(conn):
    return inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    tables = _table_names(conn)

    if 'socrates_assignment' not in tables:
        op.create_table(
            'socrates_assignment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('topic', sa.String(length=300), nullable=False),
            sa.Column('instructions', sa.Text(), nullable=True),
            sa.Column('mode', sa.String(length=20), nullable=False, server_default='individual'),
            sa.Column('prompt_limit', sa.Integer(), nullable=False, server_default='15'),
            sa.Column('deadline', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['class_session.id']),
            sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_socrates_assignment_session_id', 'socrates_assignment', ['session_id'])
        op.create_index('ix_socrates_assignment_teacher_id', 'socrates_assignment', ['teacher_id'])

    if 'socrates_group' not in tables:
        op.create_table(
            'socrates_group',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['socrates_assignment.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_socrates_group_assignment_id', 'socrates_group', ['assignment_id'])

    if 'socrates_group_member' not in tables:
        op.create_table(
            'socrates_group_member',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=50), nullable=False),
            sa.Column('student_name', sa.String(length=100), nullable=True),
            sa.ForeignKeyConstraint(['group_id'], ['socrates_group.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_socrates_group_member_group_id', 'socrates_group_member', ['group_id'])
        op.create_index('ix_socrates_group_member_student_id', 'socrates_group_member', ['student_id'])

    if 'socrates_conversation' not in tables:
        op.create_table(
            'socrates_conversation',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=True),
            sa.Column('student_id', sa.String(length=50), nullable=True),
            sa.Column('student_name', sa.String(length=100), nullable=True),
            sa.Column('prompts_used', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='in_progress'),
            sa.Column('ai_evaluation_json', sa.Text(), nullable=True),
            sa.Column('teacher_mark', sa.Float(), nullable=True),
            sa.Column('teacher_comment', sa.Text(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['socrates_assignment.id']),
            sa.ForeignKeyConstraint(['group_id'], ['socrates_group.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_socrates_conversation_assignment_id', 'socrates_conversation', ['assignment_id'])
        op.create_index('ix_socrates_conversation_group_id', 'socrates_conversation', ['group_id'])
        op.create_index('ix_socrates_conversation_student_id', 'socrates_conversation', ['student_id'])

    if 'socrates_message' not in tables:
        op.create_table(
            'socrates_message',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('conversation_id', sa.Integer(), nullable=False),
            sa.Column('sender', sa.String(length=20), nullable=False),
            sa.Column('sender_student_id', sa.String(length=50), nullable=True),
            sa.Column('sender_student_name', sa.String(length=100), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['conversation_id'], ['socrates_conversation.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_socrates_message_conversation_id', 'socrates_message', ['conversation_id'])


def downgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    for table in ('socrates_message', 'socrates_conversation', 'socrates_group_member', 'socrates_group', 'socrates_assignment'):
        if table in tables:
            op.drop_table(table)
