"""Admin user list is split into role tabs."""
from blueprints.class_management.models import Teacher
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User


def _user(username, role, full_name=None, teacher_id=None):
    user = User(
        username=username,
        email=f'{username}@test.example',
        full_name=full_name or username,
        role=role,
        teacher_id=teacher_id,
    )
    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def test_admin_users_split_into_role_tabs(client, app):
    with app.app_context():
        internal = Teacher(name='Internal One', short_name='IN1', is_external=False)
        external = Teacher(name='External One', short_name='EX1', is_external=True)
        db.session.add_all([internal, external])
        db.session.flush()
        _user('admin1', 'admin', 'Administrator')
        _user('inteacher', 'teacher', 'Internal Teacher', teacher_id=internal.id)
        _user('exteacher', 'teacher', 'External Teacher', teacher_id=external.id)
        _user('officer1', 'officer', 'Office Officer')
        _user('head1', 'head', 'Discipline Head')
        _user('student1', 'student', 'A Student')

    login_client(client, 'admin1', role='admin', window_id=None)
    page = client.get('/admin/users')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for label in (
        'Internal Teacher',
        'External Teacher',
        'Officer',
        'Administrator',
        'Head of Discipline',
        'Students',
    ):
        assert label in html
    assert 'id="tab-dean"' not in html
    assert 'id="tab-teaching_assistant"' not in html
    assert 'id="tab-other"' not in html
    body = html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    assert 'Internal Teacher' in body
    assert 'External Teacher' not in body

    external_page = client.get('/admin/users?tab=external')
    external_body = external_page.get_data(as_text=True).split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    assert 'External Teacher' in external_body
    assert 'Internal Teacher' not in external_body

    students = client.get('/admin/users?tab=students')
    student_html = students.get_data(as_text=True)
    assert 'A Student' in student_html
    assert 'Office Officer' not in student_html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
