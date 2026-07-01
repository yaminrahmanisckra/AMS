"""Add window_id to Phase 2A operational tables

Revision ID: c3d4e5f6a7b8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-25 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'c3d4e5f6a7b8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def _add_window_id_column(conn, inspector, table_name, fk_name):
    if not _table_exists(inspector, table_name):
        return
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    if 'window_id' in cols:
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            fk_name,
            'operational_window',
            ['window_id'],
            ['id'],
        )
    conn.execute(text(f'UPDATE {table_name} SET window_id = 1 WHERE window_id IS NULL'))


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    tables = [
        ('duty_assignment', 'fk_duty_assignment_window'),
        ('session_archive', 'fk_session_archive_window'),
        ('exam_paper_evaluation', 'fk_exam_paper_evaluation_window'),
        ('exam_scrutinizer_invite', 'fk_exam_scrutinizer_invite_window'),
        ('exam_paper_evaluator_assignment', 'fk_exam_evaluator_assignment_window'),
        ('remuneration_form', 'fk_remuneration_form_window'),
    ]
    for table_name, fk_name in tables:
        _add_window_id_column(conn, inspector, table_name, fk_name)

    if _table_exists(inspector, 'exam_paper_evaluator_assignment'):
        cols = {c['name'] for c in inspector.get_columns('exam_paper_evaluator_assignment')}
        if 'window_id' in cols:
            if conn.dialect.name == 'sqlite':
                conn.execute(text('PRAGMA foreign_keys=OFF'))
                conn.execute(text('''
                    CREATE TABLE exam_paper_evaluator_assignment_new (
                        id INTEGER NOT NULL,
                        course_id INTEGER NOT NULL,
                        part VARCHAR(10) NOT NULL,
                        assigned_teacher_id INTEGER NOT NULL,
                        question_setter_id INTEGER,
                        is_same_person BOOLEAN,
                        academic_session VARCHAR(50) NOT NULL,
                        year VARCHAR(20) NOT NULL,
                        term VARCHAR(20) NOT NULL,
                        exam_paper_evaluation_id INTEGER,
                        assigned_by_id INTEGER,
                        window_id INTEGER,
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id),
                        CONSTRAINT uq_evaluator_assignment_window UNIQUE (
                            window_id, course_id, part, academic_session, year, term
                        ),
                        FOREIGN KEY(course_id) REFERENCES course (id),
                        FOREIGN KEY(assigned_teacher_id) REFERENCES teacher (id),
                        FOREIGN KEY(question_setter_id) REFERENCES teacher (id),
                        FOREIGN KEY(exam_paper_evaluation_id) REFERENCES exam_paper_evaluation (id),
                        FOREIGN KEY(window_id) REFERENCES operational_window (id)
                    )
                '''))
                conn.execute(text('''
                    INSERT INTO exam_paper_evaluator_assignment_new
                    (id, course_id, part, assigned_teacher_id, question_setter_id, is_same_person,
                     academic_session, year, term, exam_paper_evaluation_id, assigned_by_id,
                     window_id, created_at, updated_at)
                    SELECT id, course_id, part, assigned_teacher_id, question_setter_id, is_same_person,
                           academic_session, year, term, exam_paper_evaluation_id, assigned_by_id,
                           window_id, created_at, updated_at
                    FROM exam_paper_evaluator_assignment
                '''))
                conn.execute(text('DROP TABLE exam_paper_evaluator_assignment'))
                conn.execute(text(
                    'ALTER TABLE exam_paper_evaluator_assignment_new '
                    'RENAME TO exam_paper_evaluator_assignment'
                ))
                conn.execute(text('PRAGMA foreign_keys=ON'))
            else:
                try:
                    with op.batch_alter_table('exam_paper_evaluator_assignment', schema=None) as batch_op:
                        batch_op.drop_constraint('uq_evaluator_assignment', type_='unique')
                except Exception:
                    pass
                try:
                    with op.batch_alter_table('exam_paper_evaluator_assignment', schema=None) as batch_op:
                        batch_op.create_unique_constraint(
                            'uq_evaluator_assignment_window',
                            ['window_id', 'course_id', 'part', 'academic_session', 'year', 'term'],
                        )
                except Exception:
                    pass


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if _table_exists(inspector, 'exam_paper_evaluator_assignment'):
        cols = {c['name'] for c in inspector.get_columns('exam_paper_evaluator_assignment')}
        if 'window_id' in cols:
            if conn.dialect.name == 'sqlite':
                pass
            else:
                try:
                    with op.batch_alter_table('exam_paper_evaluator_assignment', schema=None) as batch_op:
                        batch_op.drop_constraint('uq_evaluator_assignment_window', type_='unique')
                except Exception:
                    pass
                try:
                    with op.batch_alter_table('exam_paper_evaluator_assignment', schema=None) as batch_op:
                        batch_op.create_unique_constraint(
                            'uq_evaluator_assignment',
                            ['course_id', 'part', 'academic_session', 'year', 'term'],
                        )
                except Exception:
                    pass

    tables = [
        'remuneration_form',
        'exam_paper_evaluator_assignment',
        'exam_scrutinizer_invite',
        'exam_paper_evaluation',
        'session_archive',
        'duty_assignment',
    ]
    for table_name in tables:
        if not _table_exists(inspector, table_name):
            continue
        cols = {c['name'] for c in inspector.get_columns(table_name)}
        if 'window_id' not in cols:
            continue
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            try:
                batch_op.drop_constraint(f'fk_{table_name}_window', type_='foreignkey')
            except Exception:
                pass
            batch_op.drop_column('window_id')
