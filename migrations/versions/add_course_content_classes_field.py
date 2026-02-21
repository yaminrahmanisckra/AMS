"""Add course_content_classes field to course_outline

Revision ID: add_classes_field
Revises: 4d5f3fe554cb
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_course_content_classes'
down_revision = '4d5f3fe554cb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('course_outline',
        sa.Column('course_content_classes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('course_outline', 'course_content_classes')
