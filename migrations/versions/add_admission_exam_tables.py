"""Add Admission Exam tables (cycle, committee member, candidate)

Revision ID: add_admission_exam
Revises: add_alumni_payload
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_admission_exam'
down_revision = 'add_alumni_payload'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admission_cycle',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('public_token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('fee_amount', sa.String(length=20), nullable=True),
        sa.Column('rocket_account_number', sa.String(length=50), nullable=True),
        sa.Column('apply_start', sa.DateTime(), nullable=True),
        sa.Column('apply_end', sa.DateTime(), nullable=True),
        sa.Column('app_id_prefix', sa.String(length=20), nullable=False, server_default='APP'),
        sa.Column('roll_prefix', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('roll_start', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('admit_published', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('exam_date', sa.String(length=120), nullable=True),
        sa.Column('exam_venue', sa.String(length=200), nullable=True),
        sa.Column('chairman_signature_path', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_token', name='uq_admission_cycle_token')
    )
    op.create_index('ix_admission_cycle_public_token', 'admission_cycle', ['public_token'])

    op.create_table(
        'admission_committee_member',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cycle_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.String(length=30), nullable=False, server_default='member'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cycle_id'], ['admission_cycle.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cycle_id', 'user_id', name='uq_admission_committee_member')
    )

    op.create_table(
        'admission_candidate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cycle_id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.String(length=40), nullable=False),
        sa.Column('pin_hash', sa.String(length=512), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('photo_path', sa.String(length=255), nullable=True),
        sa.Column('extra_fields', sa.Text(), nullable=True),
        sa.Column('rocket_txn_id', sa.String(length=60), nullable=True),
        sa.Column('rocket_sender_phone', sa.String(length=30), nullable=True),
        sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('payment_note', sa.String(length=255), nullable=True),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('application_status', sa.String(length=20), nullable=False, server_default='submitted'),
        sa.Column('roll_no', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cycle_id'], ['admission_cycle.id'], ),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', name='uq_admission_candidate_app_id'),
        sa.UniqueConstraint('cycle_id', 'roll_no', name='uq_admission_candidate_roll')
    )
    op.create_index('ix_admission_candidate_application_id', 'admission_candidate', ['application_id'])


def downgrade():
    op.drop_index('ix_admission_candidate_application_id', table_name='admission_candidate')
    op.drop_table('admission_candidate')
    op.drop_table('admission_committee_member')
    op.drop_index('ix_admission_cycle_public_token', table_name='admission_cycle')
    op.drop_table('admission_cycle')
