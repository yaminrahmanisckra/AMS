"""Add window-scoped curriculum applicable batches and course offered tables

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-07-01 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'curriculum_applicable_batch'):
        op.create_table(
            'curriculum_applicable_batch',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('curriculum_id', sa.Integer(), nullable=False),
            sa.Column('window_id', sa.Integer(), nullable=False),
            sa.Column('applicable_batches', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['curriculum_id'], ['curriculum.id']),
            sa.ForeignKeyConstraint(['window_id'], ['operational_window.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'curriculum_id', 'window_id',
                name='uq_curriculum_applicable_batch_window',
            ),
        )
        op.create_index(
            'ix_curriculum_applicable_batch_window_id',
            'curriculum_applicable_batch',
            ['window_id'],
            unique=False,
        )

    if not _table_exists(inspector, 'course_window_offered'):
        op.create_table(
            'course_window_offered',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('course_id', sa.Integer(), nullable=False),
            sa.Column('window_id', sa.Integer(), nullable=False),
            sa.Column('offered', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['course_id'], ['course.id']),
            sa.ForeignKeyConstraint(['window_id'], ['operational_window.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('course_id', 'window_id', name='uq_course_window_offered'),
        )
        op.create_index(
            'ix_course_window_offered_window_id',
            'course_window_offered',
            ['window_id'],
            unique=False,
        )

    if _table_exists(inspector, 'curriculum'):
        conn.execute(text('''
            INSERT INTO curriculum_applicable_batch (curriculum_id, window_id, applicable_batches, created_at, updated_at)
            SELECT id, 1, applicable_batches, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM curriculum
            WHERE applicable_batches IS NOT NULL
              AND TRIM(applicable_batches) != ''
              AND id NOT IN (
                  SELECT curriculum_id FROM curriculum_applicable_batch WHERE window_id = 1
              )
        '''))

    if _table_exists(inspector, 'course'):
        conn.execute(text('''
            INSERT INTO course_window_offered (course_id, window_id, offered, created_at, updated_at)
            SELECT id, 1, offered, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM course
            WHERE id NOT IN (
                SELECT course_id FROM course_window_offered WHERE window_id = 1
            )
        '''))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if _table_exists(inspector, 'course_window_offered'):
        op.drop_index('ix_course_window_offered_window_id', table_name='course_window_offered')
        op.drop_table('course_window_offered')

    if _table_exists(inspector, 'curriculum_applicable_batch'):
        op.drop_index('ix_curriculum_applicable_batch_window_id', table_name='curriculum_applicable_batch')
        op.drop_table('curriculum_applicable_batch')
