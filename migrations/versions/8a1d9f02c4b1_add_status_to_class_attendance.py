"""add_status_to_class_attendance

Revision ID: 8a1d9f02c4b1
Revises: 7f2c1a9d4b6e, add_alumni_payload, add_question_bank_folder, add_teacher_id_users, survey_read_star_001
Create Date: 2026-05-04 17:35:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a1d9f02c4b1'
down_revision = (
    '7f2c1a9d4b6e',
    'add_alumni_payload',
    'add_question_bank_folder',
    'add_teacher_id_users',
    'survey_read_star_001',
)
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'class_attendance',
        sa.Column('status', sa.String(length=20), nullable=False, server_default='absent')
    )
    op.execute(
        "UPDATE class_attendance "
        "SET status = CASE WHEN is_present = 1 THEN 'present' ELSE 'absent' END"
    )


def downgrade():
    op.drop_column('class_attendance', 'status')
