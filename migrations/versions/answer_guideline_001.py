"""Answer guideline table for Admin Dashboard uploads

Revision ID: answer_guideline_001
Revises: notif_window_id_001
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'answer_guideline_001'
down_revision = 'notif_window_id_001'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'answer_guideline' in inspector.get_table_names():
        return
    op.create_table(
        'answer_guideline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('uploaded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_answer_guideline_uploaded_by_user_id', 'answer_guideline', ['uploaded_by_user_id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'answer_guideline' not in inspector.get_table_names():
        return
    try:
        op.drop_index('ix_answer_guideline_uploaded_by_user_id', table_name='answer_guideline')
    except Exception:
        pass
    op.drop_table('answer_guideline')
