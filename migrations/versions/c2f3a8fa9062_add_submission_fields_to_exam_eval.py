"""Add submission tracking to exam paper evaluation

Revision ID: c2f3a8fa9062
Revises: b0d9f4ab9d1e
Create Date: 2025-11-26 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2f3a8fa9062'
down_revision = 'b0d9f4ab9d1e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submitted_to_committee', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('submitted_at', sa.DateTime(), nullable=True))

    # remove server_default to avoid affecting future inserts automatically
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.alter_column('submitted_to_committee', server_default=None)


def downgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.drop_column('submitted_at')
        batch_op.drop_column('submitted_to_committee')







Revision ID: c2f3a8fa9062
Revises: b0d9f4ab9d1e
Create Date: 2025-11-26 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2f3a8fa9062'
down_revision = 'b0d9f4ab9d1e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submitted_to_committee', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('submitted_at', sa.DateTime(), nullable=True))

    # remove server_default to avoid affecting future inserts automatically
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.alter_column('submitted_to_committee', server_default=None)


def downgrade():
    with op.batch_alter_table('exam_paper_evaluation', schema=None) as batch_op:
        batch_op.drop_column('submitted_at')
        batch_op.drop_column('submitted_to_committee')























