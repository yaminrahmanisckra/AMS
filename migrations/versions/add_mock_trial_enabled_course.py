"""Admin allow-list of courses that may use Mock Trial.

Revision ID: add_mts_enabled_course
Revises: add_mock_trial
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mts_enabled_course'
down_revision = 'add_mock_trial'
branch_labels = None
depends_on = None


def _table_names(conn):
    return set(inspect(conn).get_table_names())


def upgrade():
    conn = op.get_bind()
    if 'mock_trial_enabled_course' in _table_names(conn):
        return
    op.create_table(
        'mock_trial_enabled_course',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('course_code', sa.String(length=50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['course.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('course_id', name='uq_mock_trial_enabled_course_id'),
    )
    op.create_index('ix_mock_trial_enabled_course_course_id', 'mock_trial_enabled_course', ['course_id'])
    op.create_index('ix_mock_trial_enabled_course_course_code', 'mock_trial_enabled_course', ['course_code'])


def downgrade():
    conn = op.get_bind()
    if 'mock_trial_enabled_course' in _table_names(conn):
        op.drop_table('mock_trial_enabled_course')
