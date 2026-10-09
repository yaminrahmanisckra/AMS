"""Ordered sections for group written assignments.

Revision ID: add_wa_sections
Revises: add_wa_discussion
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_wa_sections'
down_revision = 'add_wa_discussion'
branch_labels = None
depends_on = None


def _table_names(conn):
    return set(inspect(conn).get_table_names())


def upgrade():
    conn = op.get_bind()
    if 'written_assignment_section' not in _table_names(conn):
        op.create_table(
            'written_assignment_section',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('part_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=True),
            sa.Column('html_body', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['written_assignment.id']),
            sa.ForeignKeyConstraint(['part_id'], ['written_assignment_part.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_written_assignment_section_assignment_id', 'written_assignment_section', ['assignment_id'])
        op.create_index('ix_written_assignment_section_part_id', 'written_assignment_section', ['part_id'])
        op.create_index('ix_written_assignment_section_sort_order', 'written_assignment_section', ['sort_order'])


def downgrade():
    conn = op.get_bind()
    if 'written_assignment_section' in _table_names(conn):
        op.drop_table('written_assignment_section')
