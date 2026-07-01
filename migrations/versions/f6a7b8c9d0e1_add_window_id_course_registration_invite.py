"""Add window_id to course_registration_invite and window-scoped registration unique key

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-25 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if _table_exists(inspector, 'course_registration_invite'):
        cols = {c['name'] for c in inspector.get_columns('course_registration_invite')}
        if 'window_id' not in cols:
            with op.batch_alter_table('course_registration_invite', schema=None) as batch_op:
                batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_course_registration_invite_window',
                    'operational_window',
                    ['window_id'],
                    ['id'],
                )
        conn.execute(text(
            'UPDATE course_registration_invite SET window_id = 1 WHERE window_id IS NULL'
        ))
        if _table_exists(inspector, 'student_course_registration'):
            conn.execute(text('''
                UPDATE course_registration_invite
                SET window_id = (
                    SELECT scr.window_id FROM student_course_registration scr
                    WHERE scr.id = course_registration_invite.registration_id
                )
                WHERE window_id IS NULL OR window_id = 1
            '''))

    if _table_exists(inspector, 'student_course_registration'):
        if conn.dialect.name == 'sqlite':
            conn.execute(text('PRAGMA foreign_keys=OFF'))
            try:
                conn.execute(text('DROP TABLE IF EXISTS student_course_registration_old'))
            except Exception:
                pass
            conn.execute(text('''
                CREATE TABLE student_course_registration_new (
                    id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    course_id INTEGER,
                    window_id INTEGER,
                    academic_session VARCHAR(50) NOT NULL,
                    year VARCHAR(20) NOT NULL,
                    term VARCHAR(20) NOT NULL,
                    source_year VARCHAR(20),
                    source_term VARCHAR(20),
                    relevant_course_id INTEGER,
                    relevant_course_code VARCHAR(50),
                    relevant_academic_session VARCHAR(50),
                    relevant_year VARCHAR(20),
                    relevant_term VARCHAR(20),
                    use_relevant_for_committee BOOLEAN NOT NULL DEFAULT 1,
                    course_code VARCHAR(50) NOT NULL,
                    course_name VARCHAR(150) NOT NULL,
                    credit FLOAT NOT NULL,
                    course_type VARCHAR(30) NOT NULL,
                    nature VARCHAR(20) NOT NULL,
                    remark VARCHAR(20) NOT NULL,
                    carry_on BOOLEAN NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL,
                    registered_by VARCHAR(20) NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_student_course_term_window UNIQUE (
                        window_id, student_id, academic_session, year, term, course_code
                    ),
                    FOREIGN KEY(student_id) REFERENCES student (id),
                    FOREIGN KEY(course_id) REFERENCES course (id),
                    FOREIGN KEY(window_id) REFERENCES operational_window (id),
                    FOREIGN KEY(relevant_course_id) REFERENCES course (id)
                )
            '''))
            conn.execute(text('''
                INSERT INTO student_course_registration_new
                SELECT id, student_id, course_id, window_id, academic_session, year, term,
                       source_year, source_term, relevant_course_id, relevant_course_code,
                       relevant_academic_session, relevant_year, relevant_term,
                       COALESCE(use_relevant_for_committee, 1), course_code, course_name, credit,
                       course_type, nature, remark, COALESCE(carry_on, 0), status, registered_by,
                       created_at, updated_at
                FROM student_course_registration
            '''))
            conn.execute(text('DROP TABLE student_course_registration'))
            conn.execute(text(
                'ALTER TABLE student_course_registration_new RENAME TO student_course_registration'
            ))
            conn.execute(text('PRAGMA foreign_keys=ON'))
        else:
            try:
                with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
                    batch_op.drop_constraint('uq_student_course_term', type_='unique')
            except Exception:
                pass
            try:
                with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
                    batch_op.create_unique_constraint(
                        'uq_student_course_term_window',
                        ['window_id', 'student_id', 'academic_session', 'year', 'term', 'course_code'],
                    )
            except Exception:
                pass


def downgrade():
    pass
