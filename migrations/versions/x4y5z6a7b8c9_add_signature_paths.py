"""Add candidate and user signature_path columns

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'x4y5z6a7b8c9'
down_revision = 'w3x4y5z6a7b8'
branch_labels = None
depends_on = None


def _add_col(inspector, table, name, column):
    if table not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns(table)}
    if name in cols:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.add_column(column)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    _add_col(
        inspector, 'admission_candidate', 'signature_path',
        sa.Column('signature_path', sa.String(length=255), nullable=True),
    )
    # User table may be named users
    for table in ('users', 'user'):
        if table in inspector.get_table_names():
            _add_col(
                inspector, table, 'signature_path',
                sa.Column('signature_path', sa.String(length=255), nullable=True),
            )
            break


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_candidate' in inspector.get_table_names():
        cols = {c['name'] for c in inspector.get_columns('admission_candidate')}
        if 'signature_path' in cols:
            with op.batch_alter_table('admission_candidate', schema=None) as batch_op:
                batch_op.drop_column('signature_path')
    for table in ('users', 'user'):
        if table not in inspector.get_table_names():
            continue
        cols = {c['name'] for c in inspector.get_columns(table)}
        if 'signature_path' in cols:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.drop_column('signature_path')
        break
