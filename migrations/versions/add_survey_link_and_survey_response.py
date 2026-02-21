"""Add survey_link, survey_response; add survey_link_id to alumni_survey_response

Revision ID: add_survey_link
Revises: bb92084bacee
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_survey_link'
down_revision = 'bb92084bacee'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'survey_link',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_type', sa.String(32), nullable=False),
        sa.Column('access_code', sa.String(64), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('committee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['committee_id'], ['psac_committee.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('access_code', name='uq_survey_link_access_code')
    )

    op.create_table(
        'survey_response',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_type', sa.String(32), nullable=False),
        sa.Column('survey_link_id', sa.Integer(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['survey_link_id'], ['survey_link.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.add_column('alumni_survey_response', sa.Column('survey_link_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_alumni_survey_response_survey_link',
        'alumni_survey_response', 'survey_link',
        ['survey_link_id'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_alumni_survey_response_survey_link', 'alumni_survey_response', type_='foreignkey')
    op.drop_column('alumni_survey_response', 'survey_link_id')
    op.drop_table('survey_response')
    op.drop_table('survey_link')
