"""Add OperationalWindow model and window_id to operational tables

Revision ID: f1a2b3c4d5e6
Revises: 7f2c1a9d4b6e
Create Date: 2026-06-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'f1a2b3c4d5e6'
down_revision = '7f2c1a9d4b6e'
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, 'operational_window'):
        op.create_table(
            'operational_window',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=500), nullable=True),
            sa.Column('academic_session', sa.String(length=50), nullable=True),
            sa.Column('year', sa.String(length=50), nullable=True),
            sa.Column('term', sa.String(length=50), nullable=True),
            sa.Column('batch', sa.String(length=50), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('activated_by', sa.String(length=100), nullable=True),
            sa.Column('activated_at', sa.DateTime(), nullable=False),
            sa.Column('deactivated_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_operational_window_active', 'operational_window', ['is_active', 'status'], unique=False)

        conn.execute(text(
            "INSERT INTO operational_window "
            "(id, name, description, status, is_active, activated_at, created_at) "
            "VALUES (1, 'Window 1 (Default)', 'Existing data from before Active Window feature', "
            "'running', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))

    if _table_exists(inspector, 'course_session_assignment'):
        cols = {c['name'] for c in inspector.get_columns('course_session_assignment')}
        if 'window_id' not in cols:
            with op.batch_alter_table('course_session_assignment', schema=None) as batch_op:
                batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_course_session_assignment_window',
                    'operational_window',
                    ['window_id'],
                    ['id'],
                )
            conn.execute(text('UPDATE course_session_assignment SET window_id = 1 WHERE window_id IS NULL'))
            # SQLite: recreate table to replace old unique key with window-scoped key.
            if conn.dialect.name == 'sqlite':
                conn.execute(text('PRAGMA foreign_keys=OFF'))
                conn.execute(text('''
                    CREATE TABLE course_session_assignment_new (
                        id INTEGER NOT NULL,
                        course_id INTEGER NOT NULL,
                        curriculum_id INTEGER NOT NULL,
                        teacher_id INTEGER NOT NULL,
                        section VARCHAR(10),
                        batch VARCHAR(20),
                        year VARCHAR(50) NOT NULL,
                        term VARCHAR(50) NOT NULL,
                        academic_session VARCHAR(50),
                        window_id INTEGER,
                        session_created BOOLEAN NOT NULL,
                        session_id INTEGER,
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id),
                        CONSTRAINT uq_course_session_assignment_window UNIQUE (
                            window_id, course_id, teacher_id, section, year, term, batch
                        ),
                        FOREIGN KEY(course_id) REFERENCES course (id),
                        FOREIGN KEY(curriculum_id) REFERENCES curriculum (id),
                        FOREIGN KEY(teacher_id) REFERENCES teacher (id),
                        FOREIGN KEY(window_id) REFERENCES operational_window (id)
                    )
                '''))
                conn.execute(text('''
                    INSERT INTO course_session_assignment_new
                    (id, course_id, curriculum_id, teacher_id, section, batch, year, term,
                     academic_session, window_id, session_created, session_id, created_at, updated_at)
                    SELECT id, course_id, curriculum_id, teacher_id, section, batch, year, term,
                           academic_session, window_id, session_created, session_id, created_at, updated_at
                    FROM course_session_assignment
                '''))
                conn.execute(text('DROP TABLE course_session_assignment'))
                conn.execute(text(
                    'ALTER TABLE course_session_assignment_new RENAME TO course_session_assignment'
                ))
                conn.execute(text('PRAGMA foreign_keys=ON'))
            else:
                try:
                    with op.batch_alter_table('course_session_assignment', schema=None) as batch_op:
                        batch_op.drop_constraint('uq_course_session_assignment', type_='unique')
                except Exception:
                    pass
                try:
                    with op.batch_alter_table('course_session_assignment', schema=None) as batch_op:
                        batch_op.create_unique_constraint(
                            'uq_course_session_assignment_window',
                            ['window_id', 'course_id', 'teacher_id', 'section', 'year', 'term', 'batch'],
                        )
                except Exception:
                    pass

    if _table_exists(inspector, 'class_session'):
        cols = {c['name'] for c in inspector.get_columns('class_session')}
        if 'window_id' not in cols:
            with op.batch_alter_table('class_session', schema=None) as batch_op:
                batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_class_session_window',
                    'operational_window',
                    ['window_id'],
                    ['id'],
                )
            conn.execute(text('UPDATE class_session SET window_id = 1 WHERE window_id IS NULL'))

    if _table_exists(inspector, 'student_course_registration'):
        cols = {c['name'] for c in inspector.get_columns('student_course_registration')}
        if 'window_id' not in cols:
            with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
                batch_op.add_column(sa.Column('window_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_student_course_registration_window',
                    'operational_window',
                    ['window_id'],
                    ['id'],
                )
            conn.execute(text('UPDATE student_course_registration SET window_id = 1 WHERE window_id IS NULL'))


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if _table_exists(inspector, 'student_course_registration'):
        cols = {c['name'] for c in inspector.get_columns('student_course_registration')}
        if 'window_id' in cols:
            with op.batch_alter_table('student_course_registration', schema=None) as batch_op:
                batch_op.drop_constraint('fk_student_course_registration_window', type_='foreignkey')
                batch_op.drop_column('window_id')

    if _table_exists(inspector, 'class_session'):
        cols = {c['name'] for c in inspector.get_columns('class_session')}
        if 'window_id' in cols:
            with op.batch_alter_table('class_session', schema=None) as batch_op:
                batch_op.drop_constraint('fk_class_session_window', type_='foreignkey')
                batch_op.drop_column('window_id')

    if _table_exists(inspector, 'course_session_assignment'):
        cols = {c['name'] for c in inspector.get_columns('course_session_assignment')}
        if 'window_id' in cols:
            try:
                with op.batch_alter_table('course_session_assignment', schema=None) as batch_op:
                    batch_op.drop_constraint('uq_course_session_assignment_window', type_='unique')
            except Exception:
                pass
            with op.batch_alter_table('course_session_assignment', schema=None) as batch_op:
                batch_op.drop_constraint('fk_course_session_assignment_window', type_='foreignkey')
                batch_op.drop_column('window_id')
            try:
                with op.batch_alter_table('course_session_assignment', schema=None) as batch_op:
                    batch_op.create_unique_constraint(
                        'uq_course_session_assignment',
                        ['course_id', 'teacher_id', 'section', 'year', 'term', 'batch'],
                    )
            except Exception:
                pass

    if _table_exists(inspector, 'operational_window'):
        op.drop_index('idx_operational_window_active', table_name='operational_window')
        op.drop_table('operational_window')
