"""Merge all migration heads

Revision ID: d2428cff2ac8
Revises: 3002f25a49ae, a4b5c6d7e8f9, routine_enhance_001
Create Date: 2026-01-12 15:59:21.380345

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2428cff2ac8'
down_revision = ('3002f25a49ae', 'a4b5c6d7e8f9', 'routine_enhance_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
