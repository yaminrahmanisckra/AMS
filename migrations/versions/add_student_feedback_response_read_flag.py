"""Add is_read flag to student_feedback_response

Revision ID: add_student_feedback_read_001
Revises: c3d9a8e14f21
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_student_feedback_read_001'
down_revision = 'c3d9a8e14f21'
branch_labels = None
depends_on = None


def _has_column(conn, table_name, column_name):
    inspector = inspect(conn)
    columns = [column['name'] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    conn = op.get_bind()
    if not _has_column(conn, 'student_feedback_response', 'is_read'):
        op.add_column(
            'student_feedback_response',
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0')
        )


def downgrade():
    conn = op.get_bind()
    if _has_column(conn, 'student_feedback_response', 'is_read'):
        op.drop_column('student_feedback_response', 'is_read')
