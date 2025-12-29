"""add_attendance_marks_manual_to_class_student

Revision ID: 3002f25a49ae
Revises: 90c91c04151e
Create Date: 2025-12-29 12:47:36.715033

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3002f25a49ae'
down_revision = '90c91c04151e'
branch_labels = None
depends_on = None


def upgrade():
    # Add attendance_marks_manual column to class_student table
    op.add_column('class_student', sa.Column('attendance_marks_manual', sa.Float(), nullable=True))


def downgrade():
    # Remove attendance_marks_manual column from class_student table
    op.drop_column('class_student', 'attendance_marks_manual')
