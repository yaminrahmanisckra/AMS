"""Smoke tests: login / logout."""
from tests.conftest import TEST_PASSWORD, login_client


def test_login_page_loads(client):
    rv = client.get('/login')
    assert rv.status_code == 200
    assert b'login' in rv.data.lower() or b'password' in rv.data.lower()


def test_login_rejects_bad_password(client, teacher_user):
    rv = client.post(
        '/login',
        data={
            'username': teacher_user['username'],
            'password': 'wrong-password',
            'active_role': 'teacher',
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200
    assert b'Invalid username or password' in rv.data or b'login' in rv.data.lower()


def test_login_success_teacher(client, teacher_user, windows):
    rv = client.post(
        '/login',
        data={
            'username': teacher_user['username'],
            'password': TEST_PASSWORD,
            'active_role': 'teacher',
        },
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess.get('active_role') == 'teacher'


def test_login_success_with_window_session(client, teacher_user, windows):
    login_client(client, teacher_user['username'], role='teacher', window_id=windows['w1_id'])
    rv = client.get('/class-management/')
    assert rv.status_code == 200


def test_logout_clears_session(client, teacher_user, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get('/logout', follow_redirects=True)
    assert rv.status_code == 200
    with client.session_transaction() as sess:
        assert '_user_id' not in sess
