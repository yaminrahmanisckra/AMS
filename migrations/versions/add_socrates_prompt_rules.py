"""Prompt timers, paste quotas, and per-conversation deadline override for Socrates.

Revision ID: add_socrates_prompt_rules
Revises: add_socrates_integrity
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_socrates_prompt_rules'
down_revision = 'add_socrates_integrity'
branch_labels = None
depends_on = None


def _add_column(inspector, table, name, column):
    columns = {col['name'] for col in inspector.get_columns(table)}
    if name not in columns:
        op.add_column(table, column)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    if 'socrates_assignment' in tables:
        _add_column(
            inspector, 'socrates_assignment', 'prompt_seconds',
            sa.Column('prompt_seconds', sa.Integer(), nullable=True),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_assignment', 'prompt_timer_include_first',
            sa.Column('prompt_timer_include_first', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_assignment', 'paste_disabled',
            sa.Column('paste_disabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_assignment', 'paste_max_words',
            sa.Column('paste_max_words', sa.Integer(), nullable=True),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_assignment', 'paste_max_events',
            sa.Column('paste_max_events', sa.Integer(), nullable=True),
        )

    if 'socrates_conversation' in tables:
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_conversation', 'paste_events_used',
            sa.Column('paste_events_used', sa.Integer(), nullable=False, server_default='0'),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_conversation', 'debate_started_at',
            sa.Column('debate_started_at', sa.DateTime(), nullable=True),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_conversation', 'prompt_deadline_at',
            sa.Column('prompt_deadline_at', sa.DateTime(), nullable=True),
        )
        inspector = inspect(conn)
        _add_column(
            inspector, 'socrates_conversation', 'deadline_override',
            sa.Column('deadline_override', sa.DateTime(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    if 'socrates_conversation' in tables:
        columns = {col['name'] for col in inspector.get_columns('socrates_conversation')}
        for name in ('deadline_override', 'prompt_deadline_at', 'debate_started_at', 'paste_events_used'):
            if name in columns:
                op.drop_column('socrates_conversation', name)

    if 'socrates_assignment' in tables:
        columns = {col['name'] for col in inspector.get_columns('socrates_assignment')}
        for name in (
            'paste_max_events', 'paste_max_words', 'paste_disabled',
            'prompt_timer_include_first', 'prompt_seconds',
        ):
            if name in columns:
                op.drop_column('socrates_assignment', name)
