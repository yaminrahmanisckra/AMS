"""Admission waiting lists (multiple named lists per cycle)

Revision ID: add_adm_waiting_lists
Revises: add_adm_result_lists
Create Date: 2026-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_adm_waiting_lists'
down_revision = 'add_adm_result_lists'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if 'admission_waiting_list' not in tables:
        op.create_table(
            'admission_waiting_list',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('cycle_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('is_published', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['cycle_id'], ['admission_cycle.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('admission_waiting_list', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_admission_waiting_list_cycle_id'), ['cycle_id'], unique=False
            )
            batch_op.alter_column('is_published', server_default=None)
            batch_op.alter_column('sort_order', server_default=None)

    tables = set(inspect(conn).get_table_names())
    if 'admission_waiting_list_member' not in tables:
        op.create_table(
            'admission_waiting_list_member',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('waiting_list_id', sa.Integer(), nullable=False),
            sa.Column('candidate_id', sa.Integer(), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['candidate_id'], ['admission_candidate.id']),
            sa.ForeignKeyConstraint(['waiting_list_id'], ['admission_waiting_list.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'waiting_list_id', 'candidate_id', name='uq_admission_waiting_member'
            ),
        )
        with op.batch_alter_table('admission_waiting_list_member', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_admission_waiting_list_member_waiting_list_id'),
                ['waiting_list_id'],
                unique=False,
            )
            batch_op.create_index(
                batch_op.f('ix_admission_waiting_list_member_candidate_id'),
                ['candidate_id'],
                unique=False,
            )
            batch_op.alter_column('position', server_default=None)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if 'admission_waiting_list_member' in tables:
        op.drop_table('admission_waiting_list_member')
    if 'admission_waiting_list' in tables:
        op.drop_table('admission_waiting_list')
