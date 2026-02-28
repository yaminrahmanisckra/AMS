"""add is_read and is_starred to survey response tables

Revision ID: survey_read_star_001
Revises: routine_enhance_001
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'survey_read_star_001'
down_revision = 'routine_enhance_001'
branch_labels = None
depends_on = None


def _has_column(conn, table, col):
    inspector = inspect(conn)
    cols = [c['name'] for c in inspector.get_columns(table)]
    return col in cols


def upgrade():
    conn = op.get_bind()
    for table, col in [('survey_response', 'is_read'), ('survey_response', 'is_starred'),
                       ('alumni_survey_response', 'is_read'), ('alumni_survey_response', 'is_starred')]:
        if not _has_column(conn, table, col):
            op.add_column(table, sa.Column(col, sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    conn = op.get_bind()
    for table, col in [('survey_response', 'is_starred'), ('survey_response', 'is_read'),
                       ('alumni_survey_response', 'is_starred'), ('alumni_survey_response', 'is_read')]:
        if _has_column(conn, table, col):
            op.drop_column(table, col)
