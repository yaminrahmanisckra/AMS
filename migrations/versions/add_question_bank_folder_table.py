"""Add question_bank_folder table

Revision ID: add_question_bank_folder
Revises: add_question_bank_file
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = 'add_question_bank_folder'
down_revision = 'add_question_bank_file'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(conn)
    if 'question_bank_folder' not in inspector.get_table_names():
        op.create_table(
            'question_bank_folder',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_question_bank_folder_name', 'question_bank_folder', ['name'], unique=True)
        op.create_index('ix_question_bank_folder_created_by_user_id', 'question_bank_folder', ['created_by_user_id'])


def downgrade():
    op.drop_index('ix_question_bank_folder_created_by_user_id', table_name='question_bank_folder')
    op.drop_index('ix_question_bank_folder_name', table_name='question_bank_folder')
    op.drop_table('question_bank_folder')

