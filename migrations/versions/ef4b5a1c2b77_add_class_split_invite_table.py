"""add class split invite table

Revision ID: ef4b5a1c2b77
Revises: d3b54b2f0e5f
Create Date: 2025-11-20 13:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef4b5a1c2b77'
down_revision = 'd3b54b2f0e5f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'class_split_invite',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('split_group_id', sa.String(length=36), nullable=False),
        sa.Column('inviter_session_id', sa.Integer(), nullable=False),
        sa.Column('inviter_teacher_id', sa.Integer(), nullable=False),
        sa.Column('invited_teacher_id', sa.Integer(), nullable=False),
        sa.Column('invited_scope', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['inviter_session_id'], ['class_session.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inviter_teacher_id'], ['teacher.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_teacher_id'], ['teacher.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_class_split_invite_split_group_id', 'class_split_invite', ['split_group_id'], unique=False)


def downgrade():
    op.drop_index('ix_class_split_invite_split_group_id', table_name='class_split_invite')
    op.drop_table('class_split_invite')





