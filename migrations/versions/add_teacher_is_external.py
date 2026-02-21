"""Add is_external to teacher (External Teacher category)

Revision ID: teacher_external_001
Revises: saved_routine_break_001
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'teacher_external_001'
down_revision = 'saved_routine_break_001'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('teacher')]
    if 'is_external' not in cols:
        with op.batch_alter_table('teacher', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_external', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    try:
        with op.batch_alter_table('teacher', schema=None) as batch_op:
            batch_op.drop_column('is_external')
    except Exception:
        pass
