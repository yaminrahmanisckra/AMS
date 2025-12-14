"""merge_heads

Revision ID: 30a063eccd86
Revises: ('a1b2c3d4e5f6', 'add_carry_on_registration')
Create Date: 2025-12-14 15:23:57.295932

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '30a063eccd86'
down_revision = ('a1b2c3d4e5f6', 'add_carry_on_registration')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
