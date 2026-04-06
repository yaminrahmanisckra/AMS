"""Add question_bank_file table

Revision ID: add_question_bank_file
Revises: add_student_notification
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = 'add_question_bank_file'
down_revision = 'add_student_notification'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(conn)
    if 'question_bank_file' not in inspector.get_table_names():
        op.create_table(
            'question_bank_file',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subject_name', sa.String(length=200), nullable=False),
            sa.Column('course_code', sa.String(length=50), nullable=True),
            sa.Column('question_year', sa.String(length=20), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=True),
            sa.Column('uploaded_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_question_bank_file_uploaded_by_user_id',
            'question_bank_file',
            ['uploaded_by_user_id'],
        )


def downgrade():
    op.drop_index('ix_question_bank_file_uploaded_by_user_id', table_name='question_bank_file')
    op.drop_table('question_bank_file')

