"""Add Agrani Bank payment fields for admission exam

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 's9t0u1v2w3x4'
down_revision = 'r8s9t0u1v2w3'
branch_labels = None
depends_on = None


def _add_col(inspector, table, name, column):
    if table not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns(table)}
    if name in cols:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.add_column(column)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    _add_col(
        inspector, 'admission_cycle', 'payment_methods_enabled',
        sa.Column('payment_methods_enabled', sa.String(length=100), nullable=False, server_default='agrani_bank'),
    )
    _add_col(
        inspector, 'admission_cycle', 'agrani_account_number',
        sa.Column('agrani_account_number', sa.String(length=80), nullable=True),
    )
    _add_col(
        inspector, 'admission_cycle', 'agrani_account_name',
        sa.Column('agrani_account_name', sa.String(length=120), nullable=True),
    )

    _add_col(
        inspector, 'admission_candidate', 'payment_method',
        sa.Column('payment_method', sa.String(length=20), nullable=False, server_default='agrani_bank'),
    )
    _add_col(
        inspector, 'admission_candidate', 'bank_slip_txn_no',
        sa.Column('bank_slip_txn_no', sa.String(length=80), nullable=True),
    )
    _add_col(
        inspector, 'admission_candidate', 'bank_slip_path',
        sa.Column('bank_slip_path', sa.String(length=255), nullable=True),
    )

    # Drop server defaults after backfill-friendly create
    inspector = inspect(conn)
    cycle_cols = {c['name'] for c in inspector.get_columns('admission_cycle')} if 'admission_cycle' in inspector.get_table_names() else set()
    cand_cols = {c['name'] for c in inspector.get_columns('admission_candidate')} if 'admission_candidate' in inspector.get_table_names() else set()
    if 'payment_methods_enabled' in cycle_cols:
        with op.batch_alter_table('admission_cycle', schema=None) as batch_op:
            batch_op.alter_column('payment_methods_enabled', server_default=None)
    if 'payment_method' in cand_cols:
        conn.execute(text("UPDATE admission_candidate SET payment_method = 'agrani_bank' WHERE payment_method IS NULL OR payment_method = ''"))
        with op.batch_alter_table('admission_candidate', schema=None) as batch_op:
            batch_op.alter_column('payment_method', server_default=None)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    for table, cols in (
        ('admission_candidate', ['bank_slip_path', 'bank_slip_txn_no', 'payment_method']),
        ('admission_cycle', ['agrani_account_name', 'agrani_account_number', 'payment_methods_enabled']),
    ):
        if table not in inspector.get_table_names():
            continue
        existing = {c['name'] for c in inspector.get_columns(table)}
        with op.batch_alter_table(table, schema=None) as batch_op:
            for col in cols:
                if col in existing:
                    batch_op.drop_column(col)
