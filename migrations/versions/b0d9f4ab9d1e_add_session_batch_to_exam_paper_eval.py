"""Add academic_session and batch to exam paper evaluation

Revision ID: b0d9f4ab9d1e
Revises: aa974a9e0d20
Create Date: 2025-11-26 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0d9f4ab9d1e'
down_revision = 'aa974a9e0d20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('academic_session', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('batch', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.drop_column('batch')
        batch_op.drop_column('academic_session')







Revision ID: b0d9f4ab9d1e
Revises: aa974a9e0d20
Create Date: 2025-11-26 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0d9f4ab9d1e'
down_revision = 'aa974a9e0d20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('academic_session', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('batch', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.drop_column('batch')
        batch_op.drop_column('academic_session')
























