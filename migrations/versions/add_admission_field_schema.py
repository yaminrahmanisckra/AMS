"""Add field_schema JSON column to admission_cycle

Revision ID: add_admission_field_schema
Revises: add_admission_exam
Create Date: 2026-08-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_admission_field_schema'
down_revision = 'add_admission_exam'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('admission_cycle', sa.Column('field_schema', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('admission_cycle', 'field_schema')
