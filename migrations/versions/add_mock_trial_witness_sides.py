"""Witness called_by side and requested witness counts.

Revision ID: add_mts_witness_sides
Revises: add_mts_cast
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mts_witness_sides'
down_revision = 'add_mts_cast'
branch_labels = None
depends_on = None


def _columns(conn, table):
    if table not in set(inspect(conn).get_table_names()):
        return set()
    return {col['name'] for col in inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    case_cols = _columns(conn, 'mock_trial_case')
    if case_cols and 'prosecution_witness_count' not in case_cols:
        op.add_column('mock_trial_case', sa.Column('prosecution_witness_count', sa.Integer(), nullable=True))
    if case_cols and 'defence_witness_count' not in case_cols:
        op.add_column('mock_trial_case', sa.Column('defence_witness_count', sa.Integer(), nullable=True))
    witness_cols = _columns(conn, 'mock_trial_witness')
    if witness_cols and 'called_by' not in witness_cols:
        op.add_column(
            'mock_trial_witness',
            sa.Column('called_by', sa.String(length=20), nullable=False, server_default='prosecution'),
        )


def downgrade():
    conn = op.get_bind()
    if 'called_by' in _columns(conn, 'mock_trial_witness'):
        op.drop_column('mock_trial_witness', 'called_by')
    case_cols = _columns(conn, 'mock_trial_case')
    if 'defence_witness_count' in case_cols:
        op.drop_column('mock_trial_case', 'defence_witness_count')
    if 'prosecution_witness_count' in case_cols:
        op.drop_column('mock_trial_case', 'prosecution_witness_count')
