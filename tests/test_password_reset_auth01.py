"""AUTH-01: reset codes stay on the server and lock after five failures."""
import re

from user_models import PasswordResetCode, User
from tests.conftest import TEST_PASSWORD


def _capture_code(monkeypatch, captured):
    def fake_send_recovery_email(**kwargs):
        captured['text_body'] = kwargs.get('text_body') or ''
        captured['html_body'] = kwargs.get('html_body') or ''
        match = re.search(r'Your AMS verification code: (\d{6})', captured['text_body'])
        captured['code'] = match.group(1) if match else None

    monkeypatch.setattr('blueprints.auth.routes.send_recovery_email', fake_send_recovery_email)


def _request_reset(client, monkeypatch, email='teacher1@test.example'):
    captured = {}
    _capture_code(monkeypatch, captured)
    rv = client.post('/forgot-password', data={'email': email}, follow_redirects=False)
    return rv, captured


def test_reset_page_does_not_expose_code_hash(client, teacher_user, monkeypatch):
    rv, captured = _request_reset(client, monkeypatch)
    assert rv.status_code in (302, 303)
    assert captured.get('code') and len(captured['code']) == 6

    verify = client.get('/account/verify-code')
    assert verify.status_code == 200
    html = verify.data.decode('utf-8', errors='replace')
    assert 'name="challenge"' not in html
    assert captured['code'] not in html
    row = PasswordResetCode.query.one()
    assert row.code_hash not in html
    assert row.salt not in html


def test_old_signed_challenge_cannot_reset_password(client, teacher_user, app, monkeypatch):
    rv, captured = _request_reset(client, monkeypatch)
    assert rv.status_code in (302, 303)
    with client.session_transaction() as sess:
        sess['reset_challenge'] = 'forged.payload.with-hash'
        sess.pop('reset_request_id', None)

    post = client.post(
        '/account/verify-code',
        data={
            'challenge': 'forged.payload.with-hash',
            'code': captured['code'],
            'password': 'new-password-ok',
            'confirm_password': 'new-password-ok',
        },
        follow_redirects=False,
    )
    assert post.status_code in (302, 303)
    with app.app_context():
        user = User.query.filter_by(email='teacher1@test.example').first()
        assert user.check_password(TEST_PASSWORD)
        assert not user.check_password('new-password-ok')


def test_correct_code_resets_password(client, teacher_user, app, monkeypatch):
    _, captured = _request_reset(client, monkeypatch)
    post = client.post(
        '/account/verify-code',
        data={
            'code': captured['code'],
            'password': 'new-password-ok',
            'confirm_password': 'new-password-ok',
        },
        follow_redirects=False,
    )
    assert post.status_code in (302, 303)
    with app.app_context():
        user = User.query.filter_by(email='teacher1@test.example').first()
        assert user.check_password('new-password-ok')
        assert PasswordResetCode.query.filter_by(used_at=None).count() == 0


def test_five_bad_codes_lock_the_request(client, teacher_user, monkeypatch):
    rv, captured = _request_reset(client, monkeypatch)
    assert rv.status_code in (302, 303)
    for _ in range(5):
        client.post(
            '/account/verify-code',
            data={
                'code': '000000',
                'password': 'new-password-ok',
                'confirm_password': 'new-password-ok',
            },
        )
    locked = client.post(
        '/account/verify-code',
        data={
            'code': captured['code'],
            'password': 'new-password-ok',
            'confirm_password': 'new-password-ok',
        },
        follow_redirects=False,
    )
    assert locked.status_code in (302, 303)
    user = User.query.filter_by(email='teacher1@test.example').first()
    assert user.check_password(TEST_PASSWORD)


def test_unknown_email_uses_same_message(client, monkeypatch):
    captured = {}
    _capture_code(monkeypatch, captured)
    rv = client.post('/forgot-password', data={'email': 'nobody@test.example'}, follow_redirects=True)
    assert rv.status_code == 200
    assert b'verification code has been sent' in rv.data.lower()
    assert captured.get('code') is None
    assert PasswordResetCode.query.count() == 0
