"""Discussion thread and AI evaluation storage for written assignments.

Revision ID: add_wa_discussion
Revises: add_written_assignment
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_wa_discussion'
down_revision = 'add_written_assignment'
branch_labels = None
depends_on = None


def _table_names(conn):
    return set(inspect(conn).get_table_names())


def upgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    if 'written_assignment_post' not in tables:
        op.create_table(
            'written_assignment_post',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('author_role', sa.String(length=20), nullable=False),
            sa.Column('author_key', sa.String(length=80), nullable=False),
            sa.Column('author_name', sa.String(length=120), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['written_assignment.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_written_assignment_post_assignment_id', 'written_assignment_post', ['assignment_id'])
        op.create_index('ix_written_assignment_post_created_at', 'written_assignment_post', ['created_at'])
    if 'written_assignment_evaluation' not in tables:
        op.create_table(
            'written_assignment_evaluation',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('target_type', sa.String(length=20), nullable=False),
            sa.Column('target_id', sa.Integer(), nullable=False),
            sa.Column('body_json', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['written_assignment.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('assignment_id', 'target_type', 'target_id', name='uq_wa_evaluation_target'),
        )
        op.create_index(
            'ix_written_assignment_evaluation_assignment_id',
            'written_assignment_evaluation',
            ['assignment_id'],
        )


def downgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    if 'written_assignment_evaluation' in tables:
        op.drop_table('written_assignment_evaluation')
    if 'written_assignment_post' in tables:
        op.drop_table('written_assignment_post')
