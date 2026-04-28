"""Allow multiple academic sessions per curriculum year/term

Revision ID: c8f4b7d91a2e
Revises: b0d9f4ab9d1e
Create Date: 2026-04-15 19:05:00.000000
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c8f4b7d91a2e'
down_revision = 'b0d9f4ab9d1e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('curriculum_year_term', schema=None) as batch_op:
        batch_op.drop_constraint('uq_curriculum_year_term', type_='unique')
        batch_op.create_unique_constraint(
            'uq_curriculum_year_term_session',
            ['curriculum_id', 'year', 'term', 'academic_session']
        )


def downgrade():
    with op.batch_alter_table('curriculum_year_term', schema=None) as batch_op:
        batch_op.drop_constraint('uq_curriculum_year_term_session', type_='unique')
        batch_op.create_unique_constraint(
            'uq_curriculum_year_term',
            ['curriculum_id', 'year', 'term']
        )
