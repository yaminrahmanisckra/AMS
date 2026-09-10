"""Result Management Students lists only course-registered students."""
from blueprints.course_management.models import StudentCourseRegistration
from blueprints.result_management.models import RSession, RStudent
from blueprints.student_management.models import Student
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User


def _seed_result_students(app, windows):
    with app.app_context():
        registered = Student(student_id='RS001', name='Registered One', batch='28')
        class_only = Student(student_id='RS002', name='Class Only', batch='28')
        db.session.add_all([registered, class_only])
        db.session.flush()
        session = RSession(
            name='2024-25',
            year='Third',
            term='Second',
            window_id=windows['w1_id'],
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(RStudent(
            student_id='RS002',
            name='Class Only',
            session_id=session.id,
        ))
        db.session.add(StudentCourseRegistration(
            student_id=registered.id,
            academic_session='2024-25',
            year='Third',
            term='Second',
            course_code='LAW 3101',
            course_name='Jurisprudence',
            credit=3,
            course_type='Theory',
            nature='Core',
            status='finalized',
            window_id=windows['w1_id'],
        ))
        db.session.commit()
        return {'session_id': session.id, 'registered_id': registered.id}


def test_result_students_page_hides_unregistered(client, app, windows):
    ids = _seed_result_students(app, windows)
    with app.app_context():
        head = User(
            username='headstudents',
            email='headstudents@test.example',
            full_name='Head Students',
            role='head',
        )
        head.set_password(TEST_PASSWORD)
        db.session.add(head)
        db.session.commit()

    login_client(client, 'headstudents', role='head', window_id=windows['w1_id'])
    rv = client.get(f'/result-management/add_student/{ids["session_id"]}')
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert 'Registered One' in body
    assert 'RS001' in body
    assert 'Class Only' not in body
    assert 'RS002' not in body


def test_result_students_api_only_registered(client, app, windows):
    ids = _seed_result_students(app, windows)
    with app.app_context():
        head = User(
            username='headstudentsapi',
            email='headstudentsapi@test.example',
            full_name='Head Students API',
            role='head',
        )
        head.set_password(TEST_PASSWORD)
        db.session.add(head)
        db.session.commit()

    login_client(client, 'headstudentsapi', role='head', window_id=windows['w1_id'])
    rv = client.get(f'/result-management/api/students?session_id={ids["session_id"]}')
    assert rv.status_code == 200
    payload = rv.get_json()
    names = {row['name'] for row in payload['students']}
    public_ids = {row['student_id'] for row in payload['students']}
    assert names == {'Registered One'}
    assert public_ids == {'RS001'}
