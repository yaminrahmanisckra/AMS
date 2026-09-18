"""Store paste/type signals on Socrates student messages.

Revision ID: add_socrates_input_meta
Revises: add_socrates_reopen
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_socrates_input_meta'
down_revision = 'add_socrates_reopen'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'socrates_message' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('socrates_message')}
    if 'input_meta' not in columns:
        op.add_column('socrates_message', sa.Column('input_meta', sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'socrates_message' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('socrates_message')}
    if 'input_meta' in columns:
        op.drop_column('socrates_message', 'input_meta')
