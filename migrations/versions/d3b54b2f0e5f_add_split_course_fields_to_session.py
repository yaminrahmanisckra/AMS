"""add split course fields to class_session

Revision ID: d3b54b2f0e5f
Revises: bc2f8ee4c41d
Create Date: 2025-11-20 12:34:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3b54b2f0e5f'
down_revision = 'bc2f8ee4c41d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('class_session') as batch_op:
        batch_op.add_column(
            sa.Column('course_scope', sa.String(length=10), nullable=False, server_default='full')
        )
        batch_op.add_column(
            sa.Column('split_group_id', sa.String(length=36), nullable=True)
        )

    op.create_index('ix_class_session_split_group_id', 'class_session', ['split_group_id'], unique=False)

    # Remove server default to keep application-level default handling
    with op.batch_alter_table('class_session') as batch_op:
        batch_op.alter_column('course_scope', server_default=None)


def downgrade():
    op.drop_index('ix_class_session_split_group_id', table_name='class_session')
    with op.batch_alter_table('class_session') as batch_op:
        batch_op.drop_column('split_group_id')
        batch_op.drop_column('course_scope')





