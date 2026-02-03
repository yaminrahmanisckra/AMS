"""add_curriculator_editor_table

Revision ID: 4a84032bf12b
Revises: b1f220be6847
Create Date: 2026-01-29 00:05:40.233205

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a84032bf12b'
down_revision = 'b1f220be6847'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('curriculator_editor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade():
    op.drop_table('curriculator_editor')
