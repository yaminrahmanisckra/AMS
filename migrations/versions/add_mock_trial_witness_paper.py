"""IO / expert case-paper drafts.

Revision ID: add_mts_witness_paper
Revises: add_mts_witness_unlock
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_mts_witness_paper'
down_revision = 'add_mts_witness_unlock'
branch_labels = None
depends_on = None


def _tables(conn):
    return set(inspect(conn).get_table_names())


def upgrade():
    conn = op.get_bind()
    if 'mock_trial_witness_paper' in _tables(conn):
        return
    if 'mock_trial_witness' not in _tables(conn):
        return
    op.create_table(
        'mock_trial_witness_paper',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('witness_id', sa.Integer(), nullable=False),
        sa.Column('template_key', sa.String(length=80), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('body_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['mock_trial_case.id']),
        sa.ForeignKeyConstraint(['witness_id'], ['mock_trial_witness.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('witness_id', 'template_key', name='uq_mock_trial_witness_paper'),
    )
    op.create_index('ix_mock_trial_witness_paper_case_id', 'mock_trial_witness_paper', ['case_id'])
    op.create_index('ix_mock_trial_witness_paper_witness_id', 'mock_trial_witness_paper', ['witness_id'])


def downgrade():
    conn = op.get_bind()
    if 'mock_trial_witness_paper' not in _tables(conn):
        return
    op.drop_index('ix_mock_trial_witness_paper_witness_id', table_name='mock_trial_witness_paper')
    op.drop_index('ix_mock_trial_witness_paper_case_id', table_name='mock_trial_witness_paper')
    op.drop_table('mock_trial_witness_paper')
