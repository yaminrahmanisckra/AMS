"""add_year_term_type_status_prereq_to_syllabus_course_entry

Revision ID: 446138e34525
Revises: 4a84032bf12b
Create Date: 2026-01-29 00:30:02.313565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '446138e34525'
down_revision = '4a84032bf12b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('syllabus_course_entry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('year', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('term', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('entry_type', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('prerequisite_entry_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_syllabus_course_entry_prerequisite',
            'syllabus_course_entry',
            ['prerequisite_entry_id'],
            ['id'],
        )


def downgrade():
    with op.batch_alter_table('syllabus_course_entry', schema=None) as batch_op:
        batch_op.drop_constraint('fk_syllabus_course_entry_prerequisite', type_='foreignkey')
        batch_op.drop_column('prerequisite_entry_id')
        batch_op.drop_column('status')
        batch_op.drop_column('entry_type')
        batch_op.drop_column('term')
        batch_op.drop_column('year')
