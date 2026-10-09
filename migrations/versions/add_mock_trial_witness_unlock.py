"""Per-witness quiz unlock score.

Revision ID: add_mts_witness_unlock
Revises: add_mts_quiz
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mts_witness_unlock'
down_revision = 'add_mts_quiz'
branch_labels = None
depends_on = None


def _columns(conn, table):
    if table not in set(inspect(conn).get_table_names()):
        return set()
    return {col['name'] for col in inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    cols = _columns(conn, 'mock_trial_witness')
    if cols and 'unlock_min_score' not in cols:
        op.add_column(
            'mock_trial_witness',
            sa.Column('unlock_min_score', sa.Integer(), nullable=False, server_default='60'),
        )


def downgrade():
    conn = op.get_bind()
    if 'unlock_min_score' in _columns(conn, 'mock_trial_witness'):
        op.drop_column('mock_trial_witness', 'unlock_min_score')
