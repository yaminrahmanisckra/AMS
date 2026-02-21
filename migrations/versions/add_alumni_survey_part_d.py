"""Add Part D (Alumni Engagement & Suggestions) columns to alumni_survey_response

Revision ID: add_alumni_part_d
Revises: add_survey_link
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_alumni_part_d'
down_revision = 'add_survey_link'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('alumni_survey_response', sa.Column('beneficial_course_activity', sa.Text(), nullable=True))
    op.add_column('alumni_survey_response', sa.Column('alumni_association_member', sa.Boolean(), nullable=True))
    op.add_column('alumni_survey_response', sa.Column('contribute_to_discipline', sa.JSON(), nullable=True))
    op.add_column('alumni_survey_response', sa.Column('curriculum_suggestions', sa.Text(), nullable=True))
    op.add_column('alumni_survey_response', sa.Column('other_comments', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('alumni_survey_response', 'other_comments')
    op.drop_column('alumni_survey_response', 'curriculum_suggestions')
    op.drop_column('alumni_survey_response', 'contribute_to_discipline')
    op.drop_column('alumni_survey_response', 'alumni_association_member')
    op.drop_column('alumni_survey_response', 'beneficial_course_activity')
