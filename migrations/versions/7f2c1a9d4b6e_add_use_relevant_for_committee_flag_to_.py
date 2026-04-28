"""add use_relevant_for_committee flag to student registration

Revision ID: 7f2c1a9d4b6e
Revises: e4f1c2a7b9d3
Create Date: 2026-04-16 02:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f2c1a9d4b6e'
down_revision = 'e4f1c2a7b9d3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'student_course_registration',
        sa.Column(
            'use_relevant_for_committee',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true()
        )
    )


def downgrade():
    op.drop_column('student_course_registration', 'use_relevant_for_committee')
