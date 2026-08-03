"""Add tin_number to teacher

Revision ID: p6q7r8s9t0u1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20 19:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'p6q7r8s9t0u1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tin_number', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.drop_column('tin_number')
