"""Add window_id to curriculum_year_term for window-scoped session/batch config

Revision ID: h8i9j0k1l2m3
Revises: g7b8c9d0e1f2
Create Date: 2026-07-01 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'h8i9j0k1l2m3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'curriculum_year_term'):
        return

    cols = {c['name'] for c in inspector.get_columns('curriculum_year_term')}
    if 'window_id' not in cols:
        with op.batch_alter_table('curriculum_year_term', schema=None) as batch_op:
            batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_curriculum_year_term_window',
                'operational_window',
                ['window_id'],
                ['id'],
            )
            batch_op.create_index('ix_curriculum_year_term_window_id', ['window_id'], unique=False)

    conn.execute(text(
        'UPDATE curriculum_year_term SET window_id = 1 WHERE window_id IS NULL'
    ))

    if conn.dialect.name == 'sqlite':
        conn.execute(text('PRAGMA foreign_keys=OFF'))
        conn.execute(text('''
            CREATE TABLE curriculum_year_term_new (
                id INTEGER NOT NULL,
                curriculum_id INTEGER NOT NULL,
                year VARCHAR(50) NOT NULL,
                term VARCHAR(50) NOT NULL,
                batch VARCHAR(20),
                academic_session VARCHAR(50),
                window_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME,
                PRIMARY KEY (id),
                CONSTRAINT uq_curriculum_year_term_window_session UNIQUE (
                    window_id, curriculum_id, year, term, academic_session
                ),
                FOREIGN KEY(curriculum_id) REFERENCES curriculum (id),
                FOREIGN KEY(window_id) REFERENCES operational_window (id)
            )
        '''))
        conn.execute(text('''
            INSERT INTO curriculum_year_term_new
            (id, curriculum_id, year, term, batch, academic_session, window_id, created_at, updated_at)
            SELECT id, curriculum_id, year, term, batch, academic_session, window_id, created_at, updated_at
            FROM curriculum_year_term
        '''))
        conn.execute(text('DROP TABLE curriculum_year_term'))
        conn.execute(text(
            'ALTER TABLE curriculum_year_term_new RENAME TO curriculum_year_term'
        ))
        conn.execute(text('PRAGMA foreign_keys=ON'))
    else:
        for old_name in ('uq_curriculum_year_term_session', 'uq_curriculum_year_term'):
            try:
                with op.batch_alter_table('curriculum_year_term', schema=None) as batch_op:
                    batch_op.drop_constraint(old_name, type_='unique')
            except Exception:
                pass
        try:
            with op.batch_alter_table('curriculum_year_term', schema=None) as batch_op:
                batch_op.create_unique_constraint(
                    'uq_curriculum_year_term_window_session',
                    ['window_id', 'curriculum_id', 'year', 'term', 'academic_session'],
                )
        except Exception:
            pass


def downgrade():
    pass
