"""Shared pytest fixtures — SQLite test DB, Flask test client, seed helpers."""
import os
import tempfile

import pytest

# Use SQLite without DATABASE_URL so create_app skips MySQL engine options.
_test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_test_db.close()
os.environ.pop('DATABASE_URL', None)
os.environ.pop('CPANEL', None)
os.environ['FLASK_ENV'] = 'development'
os.environ.setdefault('AMS_LOG_DIR', tempfile.mkdtemp(prefix='ams_test_logs_'))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402

TEST_PASSWORD = 'pass123'


@pytest.fixture(scope='session')
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        CSRF_ENABLED=False,
        LOGIN_DISABLED=False,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{_test_db.name}',
    )
    application.config.pop('SQLALCHEMY_ENGINE_OPTIONS', None)
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def _clean_tables(app):
    with app.app_context():
        yield
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


def login_client(client, username, *, role='teacher', window_id=1, password=TEST_PASSWORD):
    """Log in via POST /login and pin active window/role in the session."""
    client.post(
        '/login',
        data={
            'username': username,
            'password': password,
            'active_role': role,
        },
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess['active_role'] = role
        if window_id is not None:
            sess['active_window_id'] = int(window_id)


@pytest.fixture
def windows(app):
    from blueprints.course_management.models import OperationalWindow

    with app.app_context():
        w1 = OperationalWindow(name='Window 1', status='running', is_active=True)
        w2 = OperationalWindow(name='Window 2', status='running', is_active=True)
        db.session.add_all([w1, w2])
        db.session.commit()
        return {'w1_id': w1.id, 'w2_id': w2.id}


@pytest.fixture
def teacher_user(app, windows):
    from blueprints.class_management.models import Teacher
    from user_models import User

    with app.app_context():
        teacher = Teacher(name='Test Teacher', short_name='TT', institute='Test Institute')
        db.session.add(teacher)
        db.session.flush()
        user = User(
            username='teacher1',
            email='teacher1@test.example',
            full_name='Test Teacher',
            role='teacher',
            teacher_id=teacher.id,
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
        return {
            'teacher_id': teacher.id,
            'user_id': user.id,
            'username': user.username,
        }


@pytest.fixture
def class_session_w1(app, teacher_user, windows):
    from blueprints.class_management.models import ClassStudent, Session
    from blueprints.student_management.models import Student as StudentMgmt

    with app.app_context():
        db.session.add(StudentMgmt(student_id='S001', name='Student One'))
        sess = Session(
            year='Fourth',
            term='First',
            academic_session='2024-25',
            window_id=windows['w1_id'],
            course_code='LAW 4103',
            course_name='Criminal Procedure',
            teacher_id=teacher_user['teacher_id'],
            course_type='theory',
            category='ug',
        )
        db.session.add(sess)
        db.session.flush()
        student = ClassStudent(
            student_id='S001',
            name='Student One',
            session_id=sess.id,
            teacher_id=teacher_user['teacher_id'],
        )
        db.session.add(student)
        db.session.commit()
        return {'session_id': sess.id, 'student_id': student.id}


@pytest.fixture
def class_session_w2(app, teacher_user, windows):
    from blueprints.class_management.models import ClassStudent, Session
    from blueprints.student_management.models import Student as StudentMgmt

    with app.app_context():
        db.session.add(StudentMgmt(student_id='S002', name='Student Two'))
        sess = Session(
            year='Fourth',
            term='First',
            academic_session='2024-25',
            window_id=windows['w2_id'],
            course_code='LAW 4103',
            course_name='Criminal Procedure W2',
            teacher_id=teacher_user['teacher_id'],
            course_type='theory',
            category='ug',
        )
        db.session.add(sess)
        db.session.flush()
        student = ClassStudent(
            student_id='S002',
            name='Student Two',
            session_id=sess.id,
            teacher_id=teacher_user['teacher_id'],
        )
        db.session.add(student)
        db.session.commit()
        return {'session_id': sess.id, 'student_id': student.id}
