"""Add admission document tags and candidate documents table

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-08-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'y5z6a7b8c9d0'
down_revision = 'x4y5z6a7b8c9'
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
        inspector, 'admission_cycle', 'document_tags',
        sa.Column('document_tags', sa.Text(), nullable=True),
    )
    if 'admission_candidate_document' not in inspector.get_table_names():
        op.create_table(
            'admission_candidate_document',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('candidate_id', sa.Integer(), nullable=False),
            sa.Column('tag', sa.String(length=120), nullable=False),
            sa.Column('file_path', sa.String(length=255), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('note', sa.String(length=255), nullable=True),
            sa.Column('verified_by', sa.Integer(), nullable=True),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['candidate_id'], ['admission_candidate.id']),
            sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_admission_candidate_document_candidate_id',
            'admission_candidate_document',
            ['candidate_id'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'admission_candidate_document' in inspector.get_table_names():
        op.drop_index(
            'ix_admission_candidate_document_candidate_id',
            table_name='admission_candidate_document',
        )
        op.drop_table('admission_candidate_document')
    if 'admission_cycle' in inspector.get_table_names():
        cols = {c['name'] for c in inspector.get_columns('admission_cycle')}
        if 'document_tags' in cols:
            with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
                batch_op.drop_column('document_tags')
