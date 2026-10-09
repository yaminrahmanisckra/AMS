"""In-AMS written assignments: individual and group essays.

Revision ID: add_written_assignment
Revises: add_message_seen_at, add_socrates_prompt_rules, add_student_feedback_read_001, p6q7r8s9t0u1
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_written_assignment'
down_revision = (
    'add_message_seen_at',
    'add_socrates_prompt_rules',
    'add_student_feedback_read_001',
    'p6q7r8s9t0u1',
)
branch_labels = None
depends_on = None


def _table_names(conn):
    return set(inspect(conn).get_table_names())


def upgrade():
    conn = op.get_bind()
    tables = _table_names(conn)

    if 'written_assignment' not in tables:
        op.create_table(
            'written_assignment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=300), nullable=False),
            sa.Column('instructions', sa.Text(), nullable=True),
            sa.Column('mode', sa.String(length=20), nullable=False, server_default='individual'),
            sa.Column('paste_disabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('paste_max_words', sa.Integer(), nullable=True),
            sa.Column('paste_max_events', sa.Integer(), nullable=True),
            sa.Column('deadline', sa.DateTime(), nullable=True),
            sa.Column('marks_out_of', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['class_session.id']),
            sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_written_assignment_session_id', 'written_assignment', ['session_id'])
        op.create_index('ix_written_assignment_teacher_id', 'written_assignment', ['teacher_id'])

    if 'written_assignment_group' not in tables:
        op.create_table(
            'written_assignment_group',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('teacher_mark', sa.Float(), nullable=True),
            sa.Column('teacher_comment', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['written_assignment.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_written_assignment_group_assignment_id', 'written_assignment_group', ['assignment_id'])

    if 'written_assignment_member' not in tables:
        op.create_table(
            'written_assignment_member',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=50), nullable=False),
            sa.Column('student_name', sa.String(length=100), nullable=True),
            sa.ForeignKeyConstraint(['group_id'], ['written_assignment_group.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_written_assignment_member_group_id', 'written_assignment_member', ['group_id'])
        op.create_index('ix_written_assignment_member_student_id', 'written_assignment_member', ['student_id'])

    if 'written_assignment_part' not in tables:
        op.create_table(
            'written_assignment_part',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=True),
            sa.Column('student_id', sa.String(length=50), nullable=False),
            sa.Column('student_name', sa.String(length=100), nullable=True),
            sa.Column('html_body', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('focus_loss_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('screenshot_hint_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('paste_events_used', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('input_meta', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deadline_exempt', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('teacher_mark', sa.Float(), nullable=True),
            sa.Column('teacher_comment', sa.Text(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['written_assignment.id']),
            sa.ForeignKeyConstraint(['group_id'], ['written_assignment_group.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('assignment_id', 'student_id', name='uq_written_part_student'),
        )
        op.create_index('ix_written_assignment_part_assignment_id', 'written_assignment_part', ['assignment_id'])
        op.create_index('ix_written_assignment_part_group_id', 'written_assignment_part', ['group_id'])
        op.create_index('ix_written_assignment_part_student_id', 'written_assignment_part', ['student_id'])


def downgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    if 'written_assignment_part' in tables:
        op.drop_table('written_assignment_part')
    if 'written_assignment_member' in tables:
        op.drop_table('written_assignment_member')
    if 'written_assignment_group' in tables:
        op.drop_table('written_assignment_group')
    if 'written_assignment' in tables:
        op.drop_table('written_assignment')
