"""Add columns/tables for phased AI integrations

Revision ID: ai_phased_integrations
Revises: o5p6q7r8s9t0
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'ai_phased_integrations'
down_revision = 'o5p6q7r8s9t0'
branch_labels = None
depends_on = None


def _add_column_if_missing(inspector, table, column, col):
    if table not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns(table)}
    if column not in existing:
        op.add_column(table, col)


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    _add_column_if_missing(
        inspector, 'question_bank_file', 'file_kind',
        sa.Column('file_kind', sa.String(length=30), nullable=False, server_default='question'),
    )
    _add_column_if_missing(
        inspector, 'question_bank_file', 'extracted_text',
        sa.Column('extracted_text', sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        inspector, 'question_bank_file', 'analysis_json',
        sa.Column('analysis_json', sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        inspector, 'question_bank_file', 'model_answers_json',
        sa.Column('model_answers_json', sa.Text(), nullable=True),
    )

    _add_column_if_missing(
        inspector, 'class_session', 'qa_ai_auto_reply',
        sa.Column('qa_ai_auto_reply', sa.Boolean(), nullable=False, server_default='0'),
    )
    _add_column_if_missing(
        inspector, 'course_question_message', 'is_ai_generated',
        sa.Column('is_ai_generated', sa.Boolean(), nullable=False, server_default='0'),
    )

    tables = inspector.get_table_names()
    if 'survey_insight_snapshot' not in tables:
        op.create_table(
            'survey_insight_snapshot',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('survey_type', sa.String(length=32), nullable=False),
            sa.Column('window_id', sa.Integer(), nullable=True),
            sa.Column('summary_json', sa.Text(), nullable=True),
            sa.Column('generated_at', sa.DateTime(), nullable=True),
            sa.Column('generated_by_user_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['window_id'], ['operational_window.id']),
            sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_survey_insight_snapshot_survey_type',
            'survey_insight_snapshot',
            ['survey_type'],
        )
        op.create_index(
            'ix_survey_insight_snapshot_window_id',
            'survey_insight_snapshot',
            ['window_id'],
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'survey_insight_snapshot' in tables:
        op.drop_index('ix_survey_insight_snapshot_window_id', table_name='survey_insight_snapshot')
        op.drop_index('ix_survey_insight_snapshot_survey_type', table_name='survey_insight_snapshot')
        op.drop_table('survey_insight_snapshot')

    def _drop(table, column):
        if table not in inspector.get_table_names():
            return
        cols = {c['name'] for c in inspector.get_columns(table)}
        if column in cols:
            op.drop_column(table, column)

    _drop('course_question_message', 'is_ai_generated')
    _drop('class_session', 'qa_ai_auto_reply')
    _drop('question_bank_file', 'model_answers_json')
    _drop('question_bank_file', 'analysis_json')
    _drop('question_bank_file', 'extracted_text')
    _drop('question_bank_file', 'file_kind')
