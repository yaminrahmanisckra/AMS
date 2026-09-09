"""AUTHZ-01/02: Routine Management is not reachable anonymously."""
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User
from extensions import db


OPEN_HTML = (
    '/routine-management/assign_course',
    '/routine-management/download_teacher_wise_pdf',
    '/routine-management/download_course_wise_pdf',
)
OPEN_JSON = (
    '/routine-management/api/get_teachers',
    '/routine-management/api/routine/load',
)


def test_anonymous_html_routes_redirect_to_login(client):
    for path in OPEN_HTML:
        rv = client.get(path, follow_redirects=False)
        assert rv.status_code in (302, 303), path
        assert '/login' in (rv.headers.get('Location') or '')


def test_anonymous_json_routes_return_401(client):
    for path in OPEN_JSON:
        rv = client.get(path, follow_redirects=False)
        assert rv.status_code == 401, path
        assert rv.is_json
        assert rv.get_json().get('error') == 'Authentication required'


def test_anonymous_cannot_create_assignment(client):
    rv = client.post('/routine-management/assign_course', data={}, follow_redirects=False)
    assert rv.status_code in (302, 303)
    assert '/login' in (rv.headers.get('Location') or '')


def test_student_cannot_assign_courses(client, app, windows):
    with app.app_context():
        user = User(
            username='student1',
            email='student1@test.example',
            full_name='Test Student',
            role='student',
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()

    login_client(client, 'student1', role='student', window_id=windows['w1_id'])
    rv = client.get('/routine-management/assign_course', follow_redirects=False)
    assert rv.status_code == 403
