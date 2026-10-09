"""Track Socrates focus-loss and screenshot hints for teacher review.

Revision ID: add_socrates_integrity
Revises: add_socrates_input_meta
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_socrates_integrity'
down_revision = 'add_socrates_input_meta'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'socrates_conversation' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('socrates_conversation')}
    if 'focus_loss_count' not in columns:
        op.add_column(
            'socrates_conversation',
            sa.Column('focus_loss_count', sa.Integer(), nullable=False, server_default='0'),
        )
    if 'screenshot_hint_count' not in columns:
        op.add_column(
            'socrates_conversation',
            sa.Column('screenshot_hint_count', sa.Integer(), nullable=False, server_default='0'),
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'socrates_conversation' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('socrates_conversation')}
    if 'screenshot_hint_count' in columns:
        op.drop_column('socrates_conversation', 'screenshot_hint_count')
    if 'focus_loss_count' in columns:
        op.drop_column('socrates_conversation', 'focus_loss_count')
