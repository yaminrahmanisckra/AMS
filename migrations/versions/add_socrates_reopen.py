"""Add extra_prompts so teachers can reopen a submitted Socrates debate.

Revision ID: add_socrates_reopen
Revises: add_socrates_companion
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_socrates_reopen'
down_revision = 'add_socrates_companion'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'socrates_conversation' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('socrates_conversation')}
    if 'extra_prompts' not in columns:
        op.add_column(
            'socrates_conversation',
            sa.Column('extra_prompts', sa.Integer(), nullable=False, server_default='0'),
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'socrates_conversation' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('socrates_conversation')}
    if 'extra_prompts' in columns:
        op.drop_column('socrates_conversation', 'extra_prompts')
