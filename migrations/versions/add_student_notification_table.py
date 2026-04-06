"""Add student_notification table for student notifications

Revision ID: add_student_notification
Revises: add_teacher_read_at
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_student_notification'
down_revision = 'add_teacher_read_at'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    if 'student_notification' not in inspector.get_table_names():
        op.create_table(
            'student_notification',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('type', sa.String(length=40), nullable=False),
            sa.Column('title', sa.String(length=300), nullable=False),
            sa.Column('link_url', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_student_notification_user_id', 'student_notification', ['user_id'])


def downgrade():
    op.drop_index('ix_student_notification_user_id', table_name='student_notification')
    op.drop_table('student_notification')
