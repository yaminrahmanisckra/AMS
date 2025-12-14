"""add carry_on to student_course_registration

Revision ID: add_carry_on_registration
Revises: c2f3a8fa9062
Create Date: 2025-12-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_carry_on_registration'
down_revision = 'c2f3a8fa9062'
branch_labels = None
depends_on = None


def upgrade():
    # Check if column exists before adding
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('student_course_registration')]
    
    if 'carry_on' not in columns:
        with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
            batch_op.add_column(sa.Column('carry_on', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove carry_on column
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('student_course_registration')]
    
    if 'carry_on' in columns:
        with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
            batch_op.drop_column('carry_on')

