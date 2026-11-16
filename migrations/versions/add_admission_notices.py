"""Add admission committee notices and per-candidate read state

Revision ID: add_adm_notices
Revises: add_adm_cand_marks
Create Date: 2026-11-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_adm_notices'
down_revision = 'add_adm_cand_marks'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if 'admission_cycle' not in tables or 'admission_candidate' not in tables:
        return
    if 'admission_notice' not in tables:
        op.create_table(
            'admission_notice',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('cycle_id', sa.Integer(), sa.ForeignKey('admission_cycle.id'), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('audience', sa.String(length=20), nullable=False, server_default='selected'),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_admission_notice_cycle_id', 'admission_notice', ['cycle_id'])
    tables = set(inspect(conn).get_table_names())
    if 'admission_notice_recipient' not in tables:
        op.create_table(
            'admission_notice_recipient',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('notice_id', sa.Integer(), sa.ForeignKey('admission_notice.id'), nullable=False),
            sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('admission_candidate.id'), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('notice_id', 'candidate_id', name='uq_admission_notice_recipient'),
        )
        op.create_index('ix_admission_notice_recipient_notice_id', 'admission_notice_recipient', ['notice_id'])
        op.create_index(
            'ix_admission_notice_recipient_candidate_id',
            'admission_notice_recipient',
            ['candidate_id'],
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if 'admission_notice_recipient' in tables:
        op.drop_table('admission_notice_recipient')
    if 'admission_notice' in tables:
        op.drop_table('admission_notice')
