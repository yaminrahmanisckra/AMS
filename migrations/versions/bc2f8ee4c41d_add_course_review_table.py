"""add course_review table

Revision ID: bc2f8ee4c41d
Revises: 3a18b98f8af3
Create Date: 2025-11-11 18:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc2f8ee4c41d'
down_revision = '3a18b98f8af3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'course_review',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('class_session.id', ondelete='CASCADE'), nullable=False),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teacher.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index(
        'ix_course_review_session_teacher',
        'course_review',
        ['session_id', 'teacher_id'],
        unique=True
    )


def downgrade():
    op.drop_index('ix_course_review_session_teacher', table_name='course_review')
    op.drop_table('course_review')

