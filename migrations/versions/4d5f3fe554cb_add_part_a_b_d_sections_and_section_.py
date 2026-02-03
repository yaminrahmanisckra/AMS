"""add_part_a_b_d_sections_and_section_assignment

Revision ID: 4d5f3fe554cb
Revises: 446138e34525
Create Date: 2026-01-29 00:50:56.110798

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d5f3fe554cb'
down_revision = '446138e34525'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('syllabus_part_a_section',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('section_key', sa.String(length=80), nullable=False),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['part_id'], ['syllabus_part.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_id', 'section_key', name='uq_part_a_section_part_key')
    )
    op.create_table('syllabus_part_b_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['part_id'], ['syllabus_part.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_id')
    )
    op.create_table('syllabus_part_d_section',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('section_key', sa.String(length=80), nullable=False),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['part_id'], ['syllabus_part.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_id', 'section_key', name='uq_part_d_section_part_key')
    )
    op.create_table('syllabus_section_assignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('section_key', sa.String(length=80), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['part_id'], ['syllabus_part.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_id', 'section_key', name='uq_section_assignment_part_key')
    )


def downgrade():
    op.drop_table('syllabus_section_assignment')
    op.drop_table('syllabus_part_d_section')
    op.drop_table('syllabus_part_b_config')
    op.drop_table('syllabus_part_a_section')
