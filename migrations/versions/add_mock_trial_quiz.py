"""Teacher-authored mock trial quiz pack.

Revision ID: add_mts_quiz
Revises: add_mts_witness_sides
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mts_quiz'
down_revision = 'add_mts_witness_sides'
branch_labels = None
depends_on = None


def _columns(conn, table):
    if table not in set(inspect(conn).get_table_names()):
        return set()
    return {col['name'] for col in inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    cols = _columns(conn, 'mock_trial_case')
    if cols and 'quiz_json' not in cols:
        op.add_column('mock_trial_case', sa.Column('quiz_json', sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if 'quiz_json' in _columns(conn, 'mock_trial_case'):
        op.drop_column('mock_trial_case', 'quiz_json')
