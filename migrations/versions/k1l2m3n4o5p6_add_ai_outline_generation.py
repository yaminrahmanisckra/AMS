"""Add AI outline generation job and log tables

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-07-02 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'ai_outline_generation_job' not in tables:
        op.create_table(
            'ai_outline_generation_job',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=True),
            sa.Column('parts_json', sa.Text(), nullable=False),
            sa.Column('part_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('partial_payload_json', sa.Text(), nullable=True),
            sa.Column('context_summary_json', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_ai_outline_generation_job_session_id', 'ai_outline_generation_job', ['session_id'])
        op.create_index('ix_ai_outline_generation_job_user_id', 'ai_outline_generation_job', ['user_id'])

    if 'ai_outline_generation_log' not in tables:
        op.create_table(
            'ai_outline_generation_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('job_id', sa.Integer(), nullable=True),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('part', sa.String(length=10), nullable=False, server_default='full'),
            sa.Column('provider', sa.String(length=30), nullable=True),
            sa.Column('model_name', sa.String(length=100), nullable=True),
            sa.Column('prompt_tokens', sa.Integer(), nullable=True),
            sa.Column('completion_tokens', sa.Integer(), nullable=True),
            sa.Column('total_tokens', sa.Integer(), nullable=True),
            sa.Column('estimated_cost_usd', sa.Float(), nullable=True),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='success'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['job_id'], ['ai_outline_generation_job.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_ai_outline_generation_log_job_id', 'ai_outline_generation_log', ['job_id'])
        op.create_index('ix_ai_outline_generation_log_session_id', 'ai_outline_generation_log', ['session_id'])
        op.create_index('ix_ai_outline_generation_log_user_id', 'ai_outline_generation_log', ['user_id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    if 'ai_outline_generation_log' in tables:
        op.drop_table('ai_outline_generation_log')
    if 'ai_outline_generation_job' in tables:
        op.drop_table('ai_outline_generation_job')
