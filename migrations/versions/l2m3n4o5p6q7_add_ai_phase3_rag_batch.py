"""Add Phase 3 AI outline tables and course file RAG columns

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-07-02 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'course_file_upload' in tables:
        cols = {c['name'] for c in inspector.get_columns('course_file_upload')}
        if 'file_category' not in cols:
            op.add_column('course_file_upload', sa.Column('file_category', sa.String(length=50), nullable=True))
        if 'extracted_text' not in cols:
            op.add_column('course_file_upload', sa.Column('extracted_text', sa.Text(), nullable=True))

    if 'ai_outline_batch_job' not in tables:
        op.create_table(
            'ai_outline_batch_job',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('academic_session', sa.String(length=50), nullable=False),
            sa.Column('year', sa.String(length=50), nullable=False),
            sa.Column('term', sa.String(length=50), nullable=False),
            sa.Column('batch', sa.String(length=50), nullable=True),
            sa.Column('items_json', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_ai_outline_batch_job_user_id', 'ai_outline_batch_job', ['user_id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    if 'ai_outline_batch_job' in tables:
        op.drop_table('ai_outline_batch_job')
    if 'course_file_upload' in tables:
        cols = {c['name'] for c in inspector.get_columns('course_file_upload')}
        if 'extracted_text' in cols:
            op.drop_column('course_file_upload', 'extracted_text')
        if 'file_category' in cols:
            op.drop_column('course_file_upload', 'file_category')
