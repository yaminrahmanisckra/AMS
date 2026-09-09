"""AUTHZ-06: multi-role accounts are limited to the session's active_role."""
from types import SimpleNamespace

from extensions import db
from role_utils import (
    get_effective_roles,
    has_role,
    has_staff_privileges,
    has_stored_admin,
    has_teacher_privileges,
    is_admin,
    is_head,
    is_officer,
)
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User


def _user(role, active=None):
    return SimpleNamespace(role=role, active_role=active)


def test_head_teacher_as_teacher_cannot_claim_head():
    user = _user('head,teacher', 'teacher')
    assert get_effective_roles(user) == ['teacher']
    assert has_role(user, 'teacher')
    assert not has_role(user, 'head')
    assert not is_head(user)
    assert has_teacher_privileges(user)
    assert has_staff_privileges(user)
    assert not is_admin(user)


def test_head_teacher_as_head_keeps_head_only():
    user = _user('head,teacher', 'head')
    assert has_role(user, 'head')
    assert not has_role(user, 'teacher')
    assert is_head(user)
    assert has_teacher_privileges(user)


def test_student_ta_as_student_has_no_ta_privileges():
    user = _user('student,teaching_assistant', 'student')
    assert has_role(user, 'student')
    assert not has_role(user, 'teaching_assistant')
    assert not has_teacher_privileges(user)
    assert not has_staff_privileges(user)


def test_student_ta_as_ta_has_no_full_teacher_privileges():
    user = _user('student,teaching_assistant', 'teaching_assistant')
    assert has_role(user, 'teaching_assistant')
    assert not has_role(user, 'student')
    assert not has_teacher_privileges(user)
    assert not has_staff_privileges(user)


def test_admin_as_teacher_is_not_admin():
    user = _user('admin,teacher', 'teacher')
    assert not is_admin(user)
    assert has_stored_admin(user)
    assert has_teacher_privileges(user)
    assert not has_role(user, 'admin')
    assert not is_head(user)
    assert not is_officer(user)


def test_admin_as_admin_keeps_admin_shortcut():
    user = _user('admin', 'admin')
    assert is_admin(user)
    assert has_role(user, 'admin')
    assert has_stored_admin(user)
    assert has_teacher_privileges(user)
    assert is_head(user)


def test_missing_active_role_uses_stored_roles():
    user = _user('head')
    assert get_effective_roles(user) == ['head']
    assert has_role(user, 'head')
    assert is_head(user)


def _create_user(username, role):
    user = User(
        username=username,
        email=f'{username}@test.example',
        full_name=username.title(),
        role=role,
    )
    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def test_head_teacher_as_teacher_cannot_add_student(client, app, windows):
    with app.app_context():
        _create_user('headteach', 'head,teacher')

    login_client(client, 'headteach', role='teacher', window_id=windows['w1_id'])
    rv = client.post(
        '/student-management/add',
        data={'student_id': 'HT001', 'name': 'Head Teach Student'},
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert rv.status_code == 403


def test_head_teacher_as_head_can_add_student(client, app, windows):
    with app.app_context():
        _create_user('headok', 'head,teacher')

    login_client(client, 'headok', role='head', window_id=windows['w1_id'])
    rv = client.post(
        '/student-management/add',
        data={'student_id': 'HO001', 'name': 'Head Ok Student'},
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert rv.status_code == 200
    assert rv.get_json().get('success') is True


def test_admin_as_teacher_cannot_open_admin(client, app, windows):
    with app.app_context():
        _create_user('admintch', 'admin,teacher')

    login_client(client, 'admintch', role='teacher', window_id=windows['w1_id'])
    rv = client.get('/admin', follow_redirects=False)
    assert rv.status_code in (302, 303)
    assert '/admin' not in (rv.headers.get('Location') or '')


def test_admin_as_admin_opens_admin(client, app):
    with app.app_context():
        _create_user('adminok', 'admin')

    login_client(client, 'adminok', role='admin', window_id=None)
    rv = client.get('/admin')
    assert rv.status_code == 200
