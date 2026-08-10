"""Add window_id to evaluation_invite (peer review invitations)

Revision ID: q7r8s9t0u1v2
Revises: add_admission_field_schema
Create Date: 2026-08-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'q7r8s9t0u1v2'
down_revision = 'add_admission_field_schema'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    if 'evaluation_invite' not in tables:
        return
    cols = {c['name'] for c in inspector.get_columns('evaluation_invite')}
    if 'window_id' not in cols:
        with op.batch_alter_table('evaluation_invite', schema=None) as batch_op:
            batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_evaluation_invite_window',
                'operational_window',
                ['window_id'],
                ['id'],
            )
            batch_op.create_index('ix_evaluation_invite_window_id', ['window_id'], unique=False)

    # Prefer the class session's window; fall back to window 1.
    conn.execute(text('''
        UPDATE evaluation_invite
        SET window_id = (
            SELECT cs.window_id FROM class_session cs
            WHERE cs.id = evaluation_invite.session_id
        )
        WHERE window_id IS NULL
    '''))
    conn.execute(text('UPDATE evaluation_invite SET window_id = 1 WHERE window_id IS NULL'))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'evaluation_invite' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('evaluation_invite')}
    if 'window_id' not in cols:
        return
    with op.batch_alter_table('evaluation_invite', schema=None) as batch_op:
        try:
            batch_op.drop_index('ix_evaluation_invite_window_id')
        except Exception:
            pass
        try:
            batch_op.drop_constraint('fk_evaluation_invite_window', type_='foreignkey')
        except Exception:
            pass
        batch_op.drop_column('window_id')
