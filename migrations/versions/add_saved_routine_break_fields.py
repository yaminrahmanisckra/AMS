"""Add break settings to saved_routine (lunch_after_slot, break_type, break_time_label)

Revision ID: saved_routine_break_001
Revises: d2428cff2ac8
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'saved_routine_break_001'
down_revision = 'd2428cff2ac8'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('saved_routine')]
    with op.batch_alter_table('saved_routine', schema=None) as batch_op:
        if 'lunch_after_slot' not in cols:
            batch_op.add_column(sa.Column('lunch_after_slot', sa.Integer(), nullable=True))
        if 'break_type' not in cols:
            batch_op.add_column(sa.Column('break_type', sa.String(length=20), nullable=True))
        if 'break_time_label' not in cols:
            batch_op.add_column(sa.Column('break_time_label', sa.String(length=100), nullable=True))


def downgrade():
    try:
        with op.batch_alter_table('saved_routine', schema=None) as batch_op:
            batch_op.drop_column('break_time_label')
            batch_op.drop_column('break_type')
            batch_op.drop_column('lunch_after_slot')
    except Exception:
        pass
