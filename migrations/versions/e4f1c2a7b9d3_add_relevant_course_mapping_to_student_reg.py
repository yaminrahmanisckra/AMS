"""add relevant course mapping to student registration

Revision ID: e4f1c2a7b9d3
Revises: 9d2a6c4b1f1e
Create Date: 2026-04-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f1c2a7b9d3'
down_revision = '9d2a6c4b1f1e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('student_course_registration', sa.Column('relevant_course_id', sa.Integer(), nullable=True))
    op.add_column('student_course_registration', sa.Column('relevant_course_code', sa.String(length=50), nullable=True))
    op.add_column('student_course_registration', sa.Column('relevant_academic_session', sa.String(length=50), nullable=True))
    op.add_column('student_course_registration', sa.Column('relevant_year', sa.String(length=20), nullable=True))
    op.add_column('student_course_registration', sa.Column('relevant_term', sa.String(length=20), nullable=True))
    op.create_foreign_key(
        'fk_scr_relevant_course_id',
        'student_course_registration',
        'course',
        ['relevant_course_id'],
        ['id'],
    )


def downgrade():
    op.drop_constraint('fk_scr_relevant_course_id', 'student_course_registration', type_='foreignkey')
    op.drop_column('student_course_registration', 'relevant_term')
    op.drop_column('student_course_registration', 'relevant_year')
    op.drop_column('student_course_registration', 'relevant_academic_session')
    op.drop_column('student_course_registration', 'relevant_course_code')
    op.drop_column('student_course_registration', 'relevant_course_id')
