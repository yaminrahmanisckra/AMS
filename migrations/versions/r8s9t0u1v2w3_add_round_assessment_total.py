"""Add round_assessment_total to class_session

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'r8s9t0u1v2w3'
down_revision = 'q7r8s9t0u1v2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'class_session' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('class_session')}
    if 'round_assessment_total' in cols:
        return
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('round_assessment_total', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.alter_column('round_assessment_total', server_default=None)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'class_session' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('class_session')}
    if 'round_assessment_total' not in cols:
        return
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.drop_column('round_assessment_total')
