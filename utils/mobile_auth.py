"""Bearer tokens for the mobile app.

Tokens are signed with the app secret and die when the password changes.
They are not Flask-Login sessions: the website cookie cannot call these routes,
and a mobile token does not sign the browser in.
"""
from __future__ import annotations

import hashlib
import hmac

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from role_utils import normalize_role_list
from user_models import User

# Time alone does not sign the phone out. A password change still invalidates the token.
MOBILE_TOKEN_MAX_AGE = 10 * 365 * 24 * 60 * 60
_TOKEN_SALT = 'ams-mobile-v1'
_TEACHER_ROLES = frozenset({'teacher', 'head', 'dean'})


class MobileAuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def mobile_audience(user) -> str | None:
    """Who the routine feed is for. Officers and admins are not included yet."""
    roles = set(normalize_role_list(getattr(user, 'role', None)))
    if roles & _TEACHER_ROLES:
        return 'teacher'
    if 'student' in roles:
        return 'student'
    return None


def issue_token(user) -> str:
    payload = {'uid': int(user.id), 'pw': _password_stamp(user)}
    return _serializer().dumps(payload)


def user_from_token(token: str) -> User:
    if not token or len(token) > 4096:
        raise MobileAuthError('invalid_token', 'Sign in again.')
    try:
        data = _serializer().loads(token, max_age=MOBILE_TOKEN_MAX_AGE)
    except SignatureExpired:
        raise MobileAuthError('invalid_token', 'Sign in again.')
    except BadSignature:
        raise MobileAuthError('invalid_token', 'Sign in again.')
    if not isinstance(data, dict):
        raise MobileAuthError('invalid_token', 'Sign in again.')

    uid = data.get('uid')
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise MobileAuthError('invalid_token', 'Sign in again.')

    user = User.query.get(uid)
    if user is None:
        raise MobileAuthError('invalid_token', 'Sign in again.')

    stamp = str(data.get('pw') or '')
    expected = _password_stamp(user)
    if len(stamp) != len(expected) or not hmac.compare_digest(stamp, expected):
        raise MobileAuthError('invalid_token', 'Sign in again.')
    return user


def _serializer() -> URLSafeTimedSerializer:
    secret = current_app.config.get('SECRET_KEY')
    if not secret:
        raise MobileAuthError('unavailable', 'Sign-in is not available right now.', 503)
    return URLSafeTimedSerializer(secret, salt=_TOKEN_SALT)


def _password_stamp(user) -> str:
    raw = getattr(user, 'password_hash', None) or ''
    return hashlib.sha256(str(raw).encode('utf-8')).hexdigest()[:16]
