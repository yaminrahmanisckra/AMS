"""Add is_external_subject to exam_paper_evaluation

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-07-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_external_subject', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.alter_column('is_external_subject', server_default=None)

    op.execute("""
        UPDATE exam_paper_evaluation
        SET is_external_subject = true
        WHERE owner_teacher_id IS NOT NULL
          AND id NOT IN (
            SELECT exam_paper_evaluation_id FROM exam_paper_evaluator_assignment
            WHERE exam_paper_evaluation_id IS NOT NULL
          )
    """)


def downgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.drop_column('is_external_subject')
