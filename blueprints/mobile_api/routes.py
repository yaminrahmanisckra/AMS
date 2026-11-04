"""JSON API for the phone app, plus a bridge into the real website."""
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_user, logout_user

from extensions import csrf, db
from user_models import User
from utils.login_throttle import clear as clear_login_throttle
from utils.login_throttle import is_locked, record_failure
from utils.mobile_auth import (
    MOBILE_TOKEN_MAX_AGE,
    MobileAuthError,
    issue_token,
    mobile_audience,
    user_from_token,
)
from utils.public_errors import api_error
from utils.rate_limit import LOGIN_IP, LOGIN_USERNAME, first_blocked, reject_too_many
from utils.request_ip import client_ip
from role_utils import normalize_role_list

mobile_api_bp = Blueprint('mobile_api', __name__, url_prefix='/api/mobile/v1')
csrf.exempt(mobile_api_bp)


def _error(code, message, status):
    response = jsonify({'ok': False, 'error': code, 'message': message})
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    return response


def _ok(payload, status=200):
    body = {'ok': True}
    body.update(payload)
    response = jsonify(body)
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    return response


def _bearer_user():
    header = request.headers.get('Authorization', '')
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise MobileAuthError('invalid_token', 'Sign in again.')
    user = user_from_token(token.strip())
    if getattr(user, 'must_change_password', False):
        raise MobileAuthError(
            'password_change_required',
            'Set a new password on the website before using the app.',
            403,
        )
    audience = mobile_audience(user)
    if audience is None:
        raise MobileAuthError(
            'role_not_supported',
            'This app is for teachers and students.',
            403,
        )
    return user, audience


def _website_role(user, audience):
    """The website session role. Heads and deans keep their own role."""
    roles = set(normalize_role_list(getattr(user, 'role', None)))
    if audience == 'teacher':
        for role in ('dean', 'head', 'teacher'):
            if role in roles:
                return role
        return 'teacher'
    return 'student'


@mobile_api_bp.route('/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error('invalid_body', 'Send username and password as JSON.', 400)

    username = str(payload.get('username') or '').strip()
    password = payload.get('password')
    if not username or not isinstance(password, str) or password == '':
        return _error('invalid_body', 'Username and password are required.', 400)
    if len(username) > 150 or len(password) > 500:
        return _error('invalid_body', 'Username and password are required.', 400)

    ip = client_ip()
    blocked = first_blocked(
        ('mobile.login.ip', ip, *LOGIN_IP),
        ('mobile.login.user', username, *LOGIN_USERNAME),
    )
    if blocked:
        return reject_too_many(blocked, json_body={
            'ok': False,
            'error': 'too_many_attempts',
            'message': 'Too many login attempts. Please try again later.',
        })
    if is_locked(username, ip):
        return _error(
            'too_many_attempts',
            'Too many failed login attempts. Please try again in a few minutes.',
            429,
        )

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        record_failure(username, ip)
        return _error('invalid_login', 'Invalid username or password.', 401)

    audience = mobile_audience(user)
    if audience is None:
        return _error('role_not_supported', 'This app is for teachers and students.', 403)
    if getattr(user, 'must_change_password', False):
        return _error(
            'password_change_required',
            'Set a new password on the website before using the app.',
            403,
        )

    try:
        token = issue_token(user)
    except MobileAuthError as exc:
        return _error(exc.code, exc.message, exc.status)

    identity = {
        'id': user.id,
        'username': user.username,
        'name': user.full_name,
        'role': audience,
    }
    clear_login_throttle(username, ip)
    current_app.logger.info('mobile login user id=%s audience=%s', identity['id'], audience)
    return _ok({
        'token': token,
        'expires_in': MOBILE_TOKEN_MAX_AGE,
        'user': identity,
    })


@mobile_api_bp.route('/me', methods=['GET'])
def me():
    try:
        user, audience = _bearer_user()
    except MobileAuthError as exc:
        return _error(exc.code, exc.message, exc.status)
    return _ok({
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.full_name,
            'role': audience,
        },
    })


def _routine_response(user, audience):
    if audience == 'student':
        from utils.dashboard_settings import is_student_dashboard_card_enabled
        if not is_student_dashboard_card_enabled('class_routine'):
            return _error(
                'feature_disabled',
                'Class routine is turned off for students.',
                403,
            )

    try:
        from blueprints.mobile_api.routine_feed import routine_payload
        payload = routine_payload(user, audience)
    except Exception as exc:
        db.session.rollback()
        response, status = api_error(exc, 'Could not load your class routine.')
        response.headers['Cache-Control'] = 'no-store'
        return response, status
    return _ok(payload)


@mobile_api_bp.route('/routine', methods=['GET'])
def routine():
    try:
        user, audience = _bearer_user()
    except MobileAuthError as exc:
        return _error(exc.code, exc.message, exc.status)
    return _routine_response(user, audience)


@mobile_api_bp.route('/routine-web', methods=['GET'])
def routine_web():
    """Routine for the website session inside the phone's browser.

    The home-screen widget reads this after the person signs in on the site.
    """
    if not getattr(current_user, 'is_authenticated', False):
        return _error('invalid_token', 'Sign in again.', 401)
    audience = mobile_audience(current_user)
    if audience is None:
        return _error('role_not_supported', 'This app is for teachers and students.', 403)
    if getattr(current_user, 'must_change_password', False):
        return _error(
            'password_change_required',
            'Set a new password on the website before using the app.',
            403,
        )
    return _routine_response(current_user, audience)


@mobile_api_bp.route('/web-session', methods=['GET'])
def web_session():
    """Turn a mobile token into the normal website session, then open that site.

    The phone's in-app browser sends the token once. After the redirect, every
    website page is the real page, so later website changes show up there.
    """
    try:
        user, audience = _bearer_user()
    except MobileAuthError as exc:
        return _error(exc.code, exc.message, exc.status)

    role = _website_role(user, audience)
    logout_user()
    session.clear()
    login_user(user, remember=False)
    session['active_role'] = role
    session.permanent = True

    from utils.window_utils import resolve_window_after_login
    next_endpoint = resolve_window_after_login(user, role)
    if next_endpoint:
        target = url_for(next_endpoint)
    elif role == 'student':
        target = url_for('student_dashboard')
    else:
        target = url_for('index')

    response = redirect(target)
    response.headers['Cache-Control'] = 'no-store'
    current_app.logger.info('mobile web session user id=%s role=%s', user.id, role)
    return response
