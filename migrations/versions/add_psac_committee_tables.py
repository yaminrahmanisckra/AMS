"""Add PSAC Committee and PSAC Committee Member tables for Self Assessment

Revision ID: add_psac_committee
Revises: add_classes_field
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_psac_committee'
down_revision = 'add_course_content_classes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'psac_committee',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('head_teacher_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['head_teacher_id'], ['teacher.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'psac_committee_member',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('committee_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('is_adhoc', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['committee_id'], ['psac_committee.id'], ),
        sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('committee_id', 'teacher_id', name='uq_psac_committee_member')
    )


def downgrade():
    op.drop_table('psac_committee_member')
    op.drop_table('psac_committee')
