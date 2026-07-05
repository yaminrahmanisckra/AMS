"""Add ai_provider_setting table for AI Course Outline generation

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-07-02 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'ai_provider_setting' in inspector.get_table_names():
        return

    op.create_table(
        'ai_provider_setting',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('api_base_url', sa.String(length=255), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='8000'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'ai_provider_setting' in inspector.get_table_names():
        op.drop_table('ai_provider_setting')
