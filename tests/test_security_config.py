"""Security helpers: production secret, Socket.IO CORS, proxy IP trust."""
import pytest
from flask import Flask

from utils.request_ip import client_ip
from utils.security_config import (
    apply_proxy_fix,
    resolve_secret_key,
    session_lifetime_seconds,
    socketio_cors_origins,
)


def test_production_rejects_default_secret(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.setenv('SECRET_KEY', 'a_very_secret_default_key')
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        resolve_secret_key()


def test_production_rejects_short_secret(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.setenv('SECRET_KEY', 'short')
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        resolve_secret_key()


def test_production_accepts_long_random_secret(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.setenv('SECRET_KEY', 'n9f2k8d1-long-enough-random-value')
    assert resolve_secret_key() == 'n9f2k8d1-long-enough-random-value'


def test_development_allows_missing_secret(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.delenv('SECRET_KEY', raising=False)
    assert resolve_secret_key()


def test_socketio_cors_is_not_wildcard_in_production(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.delenv('SOCKETIO_CORS_ORIGINS', raising=False)
    monkeypatch.setenv('PUBLIC_APP_URL', 'https://kulawams.xyz')
    origins = socketio_cors_origins()
    assert origins != '*'
    assert 'https://kulawams.xyz' in origins


def test_socketio_cors_override_list(monkeypatch):
    monkeypatch.setenv(
        'SOCKETIO_CORS_ORIGINS',
        'https://kulawams.xyz, https://www.kulawams.xyz',
    )
    assert socketio_cors_origins() == [
        'https://kulawams.xyz',
        'https://www.kulawams.xyz',
    ]


def test_proxy_fix_uses_trusted_hop_not_client_spoof(monkeypatch):
    monkeypatch.setenv('TRUST_PROXY_HOPS', '1')
    monkeypatch.setenv('FLASK_ENV', 'development')
    app = Flask(__name__)
    apply_proxy_fix(app)

    @app.route('/ip')
    def show_ip():
        return client_ip()

    client = app.test_client()
    rv = client.get('/ip', headers={'X-Forwarded-For': '1.2.3.4, 10.0.0.1'})
    assert rv.data.decode() == '10.0.0.1'


def test_without_proxy_fix_spoofed_header_is_ignored(monkeypatch):
    monkeypatch.setenv('TRUST_PROXY_HOPS', '0')
    monkeypatch.setenv('FLASK_ENV', 'development')
    app = Flask(__name__)
    apply_proxy_fix(app)

    @app.route('/ip')
    def show_ip():
        return client_ip() or 'none'

    client = app.test_client()
    rv = client.get('/ip', headers={'X-Forwarded-For': '1.2.3.4'})
    assert rv.data.decode() != '1.2.3.4'


def test_session_lifetime_default_is_twelve_hours(monkeypatch):
    monkeypatch.delenv('SESSION_LIFETIME_HOURS', raising=False)
    assert session_lifetime_seconds() == 12 * 3600


def test_session_lifetime_is_clamped(monkeypatch):
    monkeypatch.setenv('SESSION_LIFETIME_HOURS', '48')
    assert session_lifetime_seconds() == 24 * 3600
    monkeypatch.setenv('SESSION_LIFETIME_HOURS', '0')
    assert session_lifetime_seconds() == 3600
