"""Add is_external_course to class_session

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-07-05 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'n4o5p6q7r8s9'
down_revision = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_external_course', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.alter_column('is_external_course', server_default=None)


def downgrade():
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.drop_column('is_external_course')
