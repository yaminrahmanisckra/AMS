"""Startup security helpers: secret key, reverse-proxy trust, Socket.IO CORS."""
from __future__ import annotations

import os

INSECURE_SECRET_KEYS = frozenset({
    '',
    'a_very_secret_default_key',
    'your-secret-key-here',
    'your_secret_key_here',
    'your_very_secret_key_here',
    'changeme',
    'secret',
    'dev-only-insecure-secret',
})

_DEV_SOCKET_ORIGINS = (
    'http://127.0.0.1:5001',
    'http://localhost:5001',
    'http://127.0.0.1:5000',
    'http://localhost:5000',
)


def is_production() -> bool:
    env = (os.getenv('FLASK_ENV') or '').strip().lower()
    return bool(os.getenv('CPANEL')) or env == 'production'


def resolve_secret_key() -> str:
    """Return SECRET_KEY. Production refuses missing or well-known placeholders."""
    secret = (os.getenv('SECRET_KEY') or '').strip()
    if is_production():
        if secret in INSECURE_SECRET_KEYS or len(secret) < 16:
            raise RuntimeError(
                'SECRET_KEY is missing or insecure. Set a long random SECRET_KEY '
                'in the application environment (cPanel Python App → Environment).'
            )
        return secret
    return secret or 'dev-only-insecure-secret'


def trust_proxy_hops() -> int:
    """How many X-Forwarded-For values to trust. 0 means ignore the header."""
    raw = os.getenv('TRUST_PROXY_HOPS')
    if raw is not None and str(raw).strip() != '':
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    if is_production() or (os.getenv('TRUST_PROXY') or '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return 1
    return 0


def session_lifetime_seconds() -> int:
    """Idle/absolute cookie lifetime. Default 12 hours (min 1h, max 24h)."""
    raw = (os.getenv('SESSION_LIFETIME_HOURS') or '12').strip()
    try:
        hours = float(raw)
    except ValueError:
        hours = 12
    hours = max(1.0, min(hours, 24.0))
    return int(hours * 3600)


def apply_proxy_fix(app):
    """Honor X-Forwarded-For from the reverse proxy; ignore client-spoofed hops."""
    hops = trust_proxy_hops()
    app.config['TRUST_PROXY_HOPS'] = hops
    if hops <= 0:
        return
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_port=0, x_prefix=0)


def _add_origin(origins, seen, url):
    value = (url or '').strip().rstrip('/')
    if not value or value in seen:
        return
    if not value.startswith(('http://', 'https://')):
        value = 'https://' + value
    seen.add(value)
    origins.append(value)


def socketio_cors_origins():
    """Allowed Socket.IO browser origins. Never '*' unless SOCKETIO_CORS_ORIGINS=*."""
    raw = (os.getenv('SOCKETIO_CORS_ORIGINS') or '').strip()
    if raw == '*':
        return '*'
    if raw:
        return [item.strip().rstrip('/') for item in raw.split(',') if item.strip()]

    origins = []
    seen = set()
    _add_origin(origins, seen, os.getenv('PUBLIC_APP_URL'))

    domain = (os.getenv('DOMAIN') or '').strip()
    if domain:
        host = domain.replace('https://', '').replace('http://', '').split('/')[0]
        _add_origin(origins, seen, 'https://' + host)
        if host.startswith('www.'):
            _add_origin(origins, seen, 'https://' + host[4:])
        else:
            _add_origin(origins, seen, 'https://www.' + host)

    try:
        from utils.tenant import current_tenant
        _add_origin(origins, seen, current_tenant().public_url)
    except Exception:
        pass

    if is_production():
        if not origins:
            _add_origin(origins, seen, 'https://kulawams.xyz')
            _add_origin(origins, seen, 'https://www.kulawams.xyz')
        return origins

    for item in _DEV_SOCKET_ORIGINS:
        _add_origin(origins, seen, item)
    return origins
