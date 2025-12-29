"""add_attendance_manual_field_to_rmark

Revision ID: 90c91c04151e
Revises: d15c240d9970
Create Date: 2025-12-29 12:38:30.090725

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90c91c04151e'
down_revision = 'd15c240d9970'
branch_labels = None
depends_on = None


def upgrade():
    # Add attendance_manual column to result_mark table
    op.add_column('result_mark', sa.Column('attendance_manual', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    # Remove attendance_manual column from result_mark table
    op.drop_column('result_mark', 'attendance_manual')
