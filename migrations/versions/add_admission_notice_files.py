"""Add optional attachment columns on admission notices

Revision ID: add_adm_notice_files
Revises: add_adm_notices
Create Date: 2026-11-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_adm_notice_files'
down_revision = 'add_adm_notices'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_notice' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_notice')}
    with op.batch_alter_table('admission_notice', schema=None) as batch_op:
        if 'file_path' not in cols:
            batch_op.add_column(sa.Column('file_path', sa.String(length=255), nullable=True))
        if 'original_filename' not in cols:
            batch_op.add_column(sa.Column('original_filename', sa.String(length=255), nullable=True))
        if 'file_size' not in cols:
            batch_op.add_column(sa.Column('file_size', sa.Integer(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_notice' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('admission_notice')}
    with op.batch_alter_table('admission_notice', schema=None) as batch_op:
        if 'file_size' in cols:
            batch_op.drop_column('file_size')
        if 'original_filename' in cols:
            batch_op.drop_column('original_filename')
        if 'file_path' in cols:
            batch_op.drop_column('file_path')
