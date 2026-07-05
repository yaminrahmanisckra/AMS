"""Add external_assessment_mode to class_session

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-05 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'o5p6q7r8s9t0'
down_revision = 'n4o5p6q7r8s9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('external_assessment_mode', sa.String(length=20), nullable=False, server_default='best_three')
        )

    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.alter_column('external_assessment_mode', server_default=None)


def downgrade():
    with op.batch_alter_table('class_session', schema=None) as batch_op:
        batch_op.drop_column('external_assessment_mode')
