"""add_slot_number_to_class_attendance

Revision ID: c3d9a8e14f21
Revises: 8a1d9f02c4b1
Create Date: 2026-05-04 18:28:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d9a8e14f21'
down_revision = '8a1d9f02c4b1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('class_attendance', sa.Column('slot_number', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('class_attendance', 'slot_number')
