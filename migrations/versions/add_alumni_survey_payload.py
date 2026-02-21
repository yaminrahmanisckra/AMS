"""Add payload column to alumni_survey_response for Law Program Accreditation form

Revision ID: add_alumni_payload
Revises: add_alumni_part_d
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_alumni_payload'
down_revision = 'add_alumni_part_d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('alumni_survey_response', sa.Column('payload', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('alumni_survey_response', 'payload')
