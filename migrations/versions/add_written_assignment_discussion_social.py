"""Likes, replies, mentions, and attachments on assignment discussion.

Revision ID: add_wa_discuss_social
Revises: add_wa_sections
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_wa_discuss_social'
down_revision = 'add_wa_sections'
branch_labels = None
depends_on = None


def _table_names(conn):
    return set(inspect(conn).get_table_names())


def _column_names(conn, table):
    return {col['name'] for col in inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    if 'written_assignment_post' in tables:
        cols = _column_names(conn, 'written_assignment_post')
        if 'parent_id' not in cols:
            op.add_column('written_assignment_post', sa.Column('parent_id', sa.Integer(), nullable=True))
            op.create_index('ix_written_assignment_post_parent_id', 'written_assignment_post', ['parent_id'])
        if 'mentions_json' not in cols:
            op.add_column('written_assignment_post', sa.Column('mentions_json', sa.Text(), nullable=True))
    if 'written_assignment_post_vote' not in tables:
        op.create_table(
            'written_assignment_post_vote',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('author_key', sa.String(length=80), nullable=False),
            sa.Column('value', sa.SmallInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['post_id'], ['written_assignment_post.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('post_id', 'author_key', name='uq_wa_post_vote_author'),
        )
        op.create_index('ix_written_assignment_post_vote_post_id', 'written_assignment_post_vote', ['post_id'])
    if 'written_assignment_post_file' not in tables:
        op.create_table(
            'written_assignment_post_file',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('original_name', sa.String(length=255), nullable=False),
            sa.Column('stored_path', sa.String(length=500), nullable=False),
            sa.Column('mime', sa.String(length=80), nullable=True),
            sa.Column('size_bytes', sa.Integer(), nullable=True),
            sa.Column('is_image', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['post_id'], ['written_assignment_post.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_written_assignment_post_file_post_id', 'written_assignment_post_file', ['post_id'])


def downgrade():
    conn = op.get_bind()
    tables = _table_names(conn)
    if 'written_assignment_post_file' in tables:
        op.drop_table('written_assignment_post_file')
    if 'written_assignment_post_vote' in tables:
        op.drop_table('written_assignment_post_vote')
    if 'written_assignment_post' in tables:
        cols = _column_names(conn, 'written_assignment_post')
        if 'mentions_json' in cols:
            op.drop_column('written_assignment_post', 'mentions_json')
        if 'parent_id' in cols:
            op.drop_index('ix_written_assignment_post_parent_id', table_name='written_assignment_post')
            op.drop_column('written_assignment_post', 'parent_id')
