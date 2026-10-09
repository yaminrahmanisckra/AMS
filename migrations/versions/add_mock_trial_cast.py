"""Student cast: prosecution, defence, and witness players.

Revision ID: add_mts_cast
Revises: add_mts_enabled_course
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mts_cast'
down_revision = 'add_mts_enabled_course'
branch_labels = None
depends_on = None


def _columns(conn, table):
    return {col['name'] for col in inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    tables = set(inspect(conn).get_table_names())
    if 'mock_trial_witness' not in tables:
        return
    cols = _columns(conn, 'mock_trial_witness')
    if 'assigned_student_id' not in cols:
        op.add_column('mock_trial_witness', sa.Column('assigned_student_id', sa.String(length=50), nullable=True))
        op.create_index('ix_mock_trial_witness_assigned_student_id', 'mock_trial_witness', ['assigned_student_id'])
    if 'assigned_student_name' not in cols:
        op.add_column('mock_trial_witness', sa.Column('assigned_student_name', sa.String(length=100), nullable=True))
    if 'student_notes' not in cols:
        op.add_column('mock_trial_witness', sa.Column('student_notes', sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    tables = set(inspect(conn).get_table_names())
    if 'mock_trial_witness' not in tables:
        return
    cols = _columns(conn, 'mock_trial_witness')
    if 'student_notes' in cols:
        op.drop_column('mock_trial_witness', 'student_notes')
    if 'assigned_student_name' in cols:
        op.drop_column('mock_trial_witness', 'assigned_student_name')
    if 'assigned_student_id' in cols:
        op.drop_index('ix_mock_trial_witness_assigned_student_id', table_name='mock_trial_witness')
        op.drop_column('mock_trial_witness', 'assigned_student_id')
