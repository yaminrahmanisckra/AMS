"""Add source year/term to student course registration

Revision ID: 9d2a6c4b1f1e
Revises: c8f4b7d91a2e
Create Date: 2026-04-15 20:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d2a6c4b1f1e'
down_revision = 'c8f4b7d91a2e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_year', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('source_term', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
        batch_op.drop_column('source_term')
        batch_op.drop_column('source_year')
