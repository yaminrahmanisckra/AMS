"""Phase 1.1: DB-backed rate limits on login and password-reset POSTs."""
from tests.conftest import TEST_PASSWORD
from utils.rate_limit import consume


def test_consume_blocks_after_limit(app):
    with app.app_context():
        assert consume('t.scope', 'alice', 2, 3600).allowed
        assert consume('t.scope', 'alice', 2, 3600).allowed
        denied = consume('t.scope', 'alice', 2, 3600)
        assert not denied.allowed
        assert denied.retry_after >= 1
        assert consume('t.scope', 'bob', 2, 3600).allowed


def test_login_username_limit_returns_429(client, teacher_user, monkeypatch):
    monkeypatch.setattr('blueprints.auth.routes.LOGIN_USERNAME', (2, 3600))
    data = {
        'username': teacher_user['username'],
        'password': TEST_PASSWORD,
        'active_role': 'teacher',
    }
    assert client.post('/login', data=data).status_code in (200, 302, 303)
    assert client.post('/login', data=data).status_code in (200, 302, 303)
    limited = client.post('/login', data=data)
    assert limited.status_code == 429
    assert limited.headers.get('Retry-After')


def test_forgot_password_email_limit_returns_429(client, teacher_user, monkeypatch):
    monkeypatch.setattr('blueprints.auth.routes.FORGOT_EMAIL', (1, 3600))
    monkeypatch.setattr('blueprints.auth.routes.send_recovery_email', lambda **kwargs: None)
    first = client.post('/forgot-password', data={'email': 'teacher1@test.example'})
    assert first.status_code in (200, 302, 303)
    limited = client.post('/forgot-password', data={'email': 'teacher1@test.example'})
    assert limited.status_code == 429
