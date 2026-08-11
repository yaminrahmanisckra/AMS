"""Add notice and notice_target tables for Noticeboard module

Revision ID: a1b2c3d4e5f6
Revises: z6a7b8c9d0e1
Create Date: 2026-08-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'a1b2c3d4e5f6'
down_revision = 'z6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'notice' not in tables:
        op.create_table(
            'notice',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=300), nullable=False),
            sa.Column('body_html', sa.Text(), nullable=False),
            sa.Column('author_user_id', sa.Integer(), nullable=False),
            sa.Column('notice_date', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('window_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['author_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['window_id'], ['operational_window.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_notice_author_user_id', 'notice', ['author_user_id'])
        op.create_index('ix_notice_notice_date', 'notice', ['notice_date'])
        op.create_index('ix_notice_deleted_at', 'notice', ['deleted_at'])
        op.create_index('ix_notice_window_id', 'notice', ['window_id'])
    else:
        cols = {c['name'] for c in inspector.get_columns('notice')}
        if 'window_id' not in cols:
            with op.batch_alter_table('notice', schema=None) as batch_op:
                batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_notice_window',
                    'operational_window',
                    ['window_id'],
                    ['id'],
                )
                batch_op.create_index('ix_notice_window_id', ['window_id'], unique=False)

    if 'notice' in inspector.get_table_names():
        conn.execute(text('UPDATE notice SET window_id = 1 WHERE window_id IS NULL'))

    if 'notice_target' not in tables:
        op.create_table(
            'notice_target',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('notice_id', sa.Integer(), nullable=False),
            sa.Column('target_type', sa.String(length=20), nullable=False),
            sa.Column('target_value', sa.String(length=100), nullable=True),
            sa.ForeignKeyConstraint(['notice_id'], ['notice.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_notice_target_notice_id', 'notice_target', ['notice_id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    if 'notice_target' in tables:
        op.drop_index('ix_notice_target_notice_id', table_name='notice_target')
        op.drop_table('notice_target')
    if 'notice' in tables:
        cols = {c['name'] for c in inspector.get_columns('notice')}
        if 'window_id' in cols:
            with op.batch_alter_table('notice', schema=None) as batch_op:
                try:
                    batch_op.drop_index('ix_notice_window_id')
                except Exception:
                    pass
                try:
                    batch_op.drop_constraint('fk_notice_window', type_='foreignkey')
                except Exception:
                    pass
                batch_op.drop_column('window_id')
        op.drop_index('ix_notice_deleted_at', table_name='notice')
        op.drop_index('ix_notice_notice_date', table_name='notice')
        op.drop_index('ix_notice_author_user_id', table_name='notice')
        op.drop_table('notice')
