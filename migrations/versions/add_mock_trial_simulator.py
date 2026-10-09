"""Hybrid AI mock trial simulator tables.

Revision ID: add_mock_trial
Revises: add_wa_sections
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mock_trial'
down_revision = 'add_wa_sections'
branch_labels = None
depends_on = None


def _table_names(conn):
    return set(inspect(conn).get_table_names())


def upgrade():
    conn = op.get_bind()
    tables = _table_names(conn)

    if 'mock_trial_case' not in tables:
        op.create_table(
            'mock_trial_case',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=300), nullable=False),
            sa.Column('case_type', sa.String(length=40), nullable=False, server_default='murder'),
            sa.Column('extra_brief', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('current_phase', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('master_factsheet_json', sa.Text(), nullable=True),
            sa.Column('fir_json', sa.Text(), nullable=True),
            sa.Column('accused_statement_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['class_session.id']),
            sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_mock_trial_case_session_id', 'mock_trial_case', ['session_id'])
        op.create_index('ix_mock_trial_case_teacher_id', 'mock_trial_case', ['teacher_id'])
        op.create_index('ix_mock_trial_case_status', 'mock_trial_case', ['status'])

    if 'mock_trial_witness' not in tables:
        op.create_table(
            'mock_trial_witness',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('case_id', sa.Integer(), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='lay'),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('designation', sa.String(length=200), nullable=True),
            sa.Column('instruction_card_json', sa.Text(), nullable=True),
            sa.Column('is_unlocked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['case_id'], ['mock_trial_case.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_mock_trial_witness_case_id', 'mock_trial_witness', ['case_id'])

    if 'mock_trial_exhibit' not in tables:
        op.create_table(
            'mock_trial_exhibit',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('case_id', sa.Integer(), nullable=False),
            sa.Column('exhibit_key', sa.String(length=50), nullable=False, server_default='other'),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('body_json', sa.Text(), nullable=True),
            sa.Column('is_unlocked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('unlock_min_score', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['case_id'], ['mock_trial_case.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_mock_trial_exhibit_case_id', 'mock_trial_exhibit', ['case_id'])

    if 'mock_trial_team' not in tables:
        op.create_table(
            'mock_trial_team',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('case_id', sa.Integer(), nullable=False),
            sa.Column('side', sa.String(length=20), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['case_id'], ['mock_trial_case.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_mock_trial_team_case_id', 'mock_trial_team', ['case_id'])

    if 'mock_trial_team_member' not in tables:
        op.create_table(
            'mock_trial_team_member',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('team_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=50), nullable=False),
            sa.Column('student_name', sa.String(length=100), nullable=True),
            sa.ForeignKeyConstraint(['team_id'], ['mock_trial_team.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('team_id', 'student_id', name='uq_mock_trial_team_student'),
        )
        op.create_index('ix_mock_trial_team_member_team_id', 'mock_trial_team_member', ['team_id'])
        op.create_index('ix_mock_trial_team_member_student_id', 'mock_trial_team_member', ['student_id'])

    if 'mock_trial_petition' not in tables:
        op.create_table(
            'mock_trial_petition',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('case_id', sa.Integer(), nullable=False),
            sa.Column('team_id', sa.Integer(), nullable=True),
            sa.Column('petition_type', sa.String(length=20), nullable=False),
            sa.Column('draft_text', sa.Text(), nullable=True),
            sa.Column('ai_eval_json', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['case_id'], ['mock_trial_case.id']),
            sa.ForeignKeyConstraint(['team_id'], ['mock_trial_team.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_mock_trial_petition_case_id', 'mock_trial_petition', ['case_id'])
        op.create_index('ix_mock_trial_petition_team_id', 'mock_trial_petition', ['team_id'])


def downgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    for name in (
        'mock_trial_petition',
        'mock_trial_team_member',
        'mock_trial_team',
        'mock_trial_exhibit',
        'mock_trial_witness',
        'mock_trial_case',
    ):
        if name in tables:
            op.drop_table(name)
