"""Remember each teacher's main-dashboard card order

Revision ID: add_dash_card_order
Revises: add_adm_cand_marks
Create Date: 2026-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_dash_card_order'
down_revision = 'add_adm_cand_marks'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'users' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'dashboard_card_order' not in cols:
        op.add_column('users', sa.Column('dashboard_card_order', sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'users' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'dashboard_card_order' in cols:
        op.drop_column('users', 'dashboard_card_order')
