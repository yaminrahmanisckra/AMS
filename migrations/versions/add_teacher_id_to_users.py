"""Add teacher_id to users table to link User to Teacher

Revision ID: add_teacher_id_users
Revises: saved_routine_break_001
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_teacher_id_users'
down_revision = 'teacher_external_001'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('users')]
    if 'teacher_id' not in cols:
        op.add_column('users', sa.Column('teacher_id', sa.Integer(), nullable=True))
        # SQLite does not support ADD CONSTRAINT; skip FK for SQLite (referential integrity still works in app)
        if conn.dialect.name != 'sqlite':
            op.create_foreign_key('fk_users_teacher_id', 'users', 'teacher', ['teacher_id'], ['id'])


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'sqlite':
        try:
            op.drop_constraint('fk_users_teacher_id', 'users', type_='foreignkey')
        except Exception:
            pass
    try:
        op.drop_column('users', 'teacher_id')
    except Exception:
        pass
