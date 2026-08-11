import hashlib
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from user_models import User
from extensions import db
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import traceback
import sys
from utils.recovery_email import send_recovery_email
from utils.login_throttle import is_locked, record_failure, clear as clear_login_throttle
from role_utils import (
    ADMIN_ROLE,
    ROLE_CHOICES,
    SELF_SIGNUP_ROLE_CHOICES,
    SELF_SIGNUP_ROLE_KEYS,
    validate_role_selection,
    serialize_roles,
    parse_roles,
)

auth_bp = Blueprint('auth', __name__, template_folder='templates')


def _client_ip():
    """Client IP for throttle keying (supports proxy X-Forwarded-For)."""
    return (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip() or request.remote_addr or ''


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    default_login_role = 'teacher'
    selected_role = default_login_role
    student_default_password = current_app.config.get('DEFAULT_STUDENT_PASSWORD', '')
    
    if request.method == 'POST':
        # Clear any existing session before processing new login
        # This prevents session cookie reuse issues (especially with ngrok)
        if current_user.is_authenticated:
            current_app.logger.info(f"Logging out existing user: {current_user.username}")
            logout_user()
        session.clear()
        
        username = request.form.get('username')
        password = request.form.get('password')
        selected_role = request.form.get('active_role') or default_login_role
        
        current_app.logger.info(f"Login attempt for username: {username}, role: {selected_role}")
        
        def render_form():
            return render_template(
                'auth/login.html',
                all_role_choices=ROLE_CHOICES,
                selected_role=selected_role,
                username=username,
                default_student_password=student_default_password
            )
        
        if not username or not password:
            flash('Please provide both username and password.', 'error')
            return render_form()
        
        if not selected_role:
            flash('Please select the category you want to use for this session.', 'error')
            return render_form()
        
        client_ip = _client_ip()
        if is_locked(username, client_ip):
            flash('Too many failed login attempts. Please try again in a few minutes.', 'error')
            return render_form()
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            record_failure(username, client_ip)
            flash('Invalid username or password.', 'error')
            return render_form()
        
        user_roles = set(parse_roles(user.role))
        if selected_role == ADMIN_ROLE:
            if ADMIN_ROLE not in user_roles:
                flash('You do not have administrator privileges.', 'error')
                return render_form()
        else:
            if selected_role not in user_roles:
                flash('You are not assigned to that category.', 'error')
                return render_form()
        
        # Force logout any existing session first
        logout_user()
        session.clear()
        
        # Login with the new user, don't remember to prevent cookie persistence issues
        login_user(user, remember=False)
        session['active_role'] = selected_role
        clear_login_throttle(username, client_ip)
        
        current_app.logger.info(f"Successfully logged in user: {user.username} (ID: {user.id}) with role: {selected_role}")
        flash('Login successful!', 'success')
        
        from utils.window_utils import resolve_window_after_login
        next_endpoint = resolve_window_after_login(user, selected_role)
        if next_endpoint:
            target = url_for(next_endpoint)
        else:
            target = url_for('index')
        
        # Create response and ensure session cookie is properly set
        response = redirect(target)
        # Force session to be saved
        session.permanent = False
        
        # Add cache-control headers to prevent browser caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    
    # GET request handling
    # If already authenticated via ngrok, clear session to prevent cookie reuse
    if current_user.is_authenticated:
        # Check if user wants to force logout (via query parameter)
        if request.args.get('force_logout') == '1':
            logout_user()
            session.clear()
            flash('Session cleared. Please login again.', 'info')
        else:
            # If accessing via ngrok, always clear session to prevent cookie reuse
            host = request.host
            if 'ngrok' in host.lower() or 'ngrok.io' in host.lower():
                logout_user()
                session.clear()
    
    return render_template(
        'auth/login.html',
        all_role_choices=ROLE_CHOICES,
        selected_role=selected_role,
        default_student_password=student_default_password,
        username=None
    )


@auth_bp.route('/select-window', methods=['GET'])
@login_required
def select_window():
    from utils.window_utils import get_active_windows, role_needs_window_selection, user_bypasses_window_selection

    active_role = session.get('active_role')
    if user_bypasses_window_selection(current_user, active_role):
        return redirect(url_for('index'))
    if not role_needs_window_selection(active_role):
        return redirect(url_for('index'))

    windows = get_active_windows()
    if not windows:
        return redirect(url_for('auth.no_active_window'))
    if len(windows) == 1:
        from utils.window_utils import set_session_window_id
        set_session_window_id(windows[0].id)
        return redirect(url_for('index'))

    return render_template('auth/select_window.html', windows=windows)


@auth_bp.route('/set-window', methods=['POST'])
@login_required
def set_window():
    from utils.window_utils import (
        get_active_windows,
        set_session_window_id,
        role_needs_window_selection,
        user_bypasses_window_selection,
    )

    active_role = session.get('active_role')
    if user_bypasses_window_selection(current_user, active_role):
        return redirect(url_for('index'))
    if not role_needs_window_selection(active_role):
        return redirect(url_for('index'))

    try:
        window_id = int(request.form.get('window_id', ''))
    except (TypeError, ValueError):
        flash('Please select a window.', 'error')
        return redirect(url_for('auth.select_window'))

    active_ids = {w.id for w in get_active_windows()}
    if window_id not in active_ids:
        flash('Selected window is not active.', 'error')
        return redirect(url_for('auth.select_window'))

    set_session_window_id(window_id)
    flash('Window selected.', 'success')
    return redirect(url_for('index'))


@auth_bp.route('/no-active-window', methods=['GET'])
@login_required
def no_active_window():
    from utils.window_utils import get_active_windows, user_bypasses_window_selection

    active_role = session.get('active_role')
    if user_bypasses_window_selection(current_user, active_role):
        return redirect(url_for('index'))
    if get_active_windows():
        return redirect(url_for('auth.select_window'))

    return render_template('auth/no_active_window.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Get username before logout for logging
    username = current_user.username if current_user.is_authenticated else None
    
    # Logout user
    logout_user()
    
    # Clear Flask session completely
    session.clear()
    
    flash('You have been logged out.', 'info')
    
    # Create redirect response
    response = redirect(url_for('auth.login'))
    
    # Delete session cookie - match the exact settings used when creating it
    # Flask uses 'session' as default cookie name
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    
    # Delete cookie with same settings as when created
    response.set_cookie(
        session_cookie_name, 
        '', 
        expires=0, 
        path=current_app.config.get('SESSION_COOKIE_PATH', '/'),
        domain=current_app.config.get('SESSION_COOKIE_DOMAIN', None),
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
        httponly=current_app.config.get('SESSION_COOKIE_HTTPONLY', True),
        samesite=current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')
    )
    
    # Also delete remember_token if used
    response.set_cookie('remember_token', '', expires=0, path='/', domain=None)
    
    # Add cache-control headers to prevent browser caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Registration is now disabled - only admin can create accounts
    flash('User registration is disabled. Please contact the administrator to create an account.', 'error')
    return redirect(url_for('auth.login'))
    
    # Old code below (disabled)
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # No default roles - user must explicitly select from available self-signup roles
    default_roles = []
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        selected_roles = request.form.getlist('roles') or default_roles
        
        def render_form():
            return render_template('auth/register.html', role_choices=SELF_SIGNUP_ROLE_CHOICES, selected_roles=selected_roles)
        
        if not all([username, email, full_name, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_form()
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_form()
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_form()
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_form()
        
        if not selected_roles:
            flash('Please select at least one role/category.', 'error')
            return render_form()
        
        disallowed = [role for role in selected_roles if role not in SELF_SIGNUP_ROLE_KEYS]
        if disallowed:
            if 'student' in disallowed:
                flash('Student accounts are created by administration. Please contact the office for student access.', 'error')
            elif 'teacher' in disallowed:
                flash('Teacher accounts are created by administration. Please contact the admin to create your account.', 'error')
            else:
                flash(f'The following roles cannot be self-registered: {", ".join(disallowed)}. Please contact administration.', 'error')
            return render_form()

        is_valid, result = validate_role_selection(selected_roles)
        if not is_valid:
            flash(result, 'error')
            return render_form()
        
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=serialize_roles(result)
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', role_choices=SELF_SIGNUP_ROLE_CHOICES, selected_roles=default_roles)

def get_serializer():
    secret = current_app.config.get('SECRET_KEY', 'a_very_secret_default_key')
    return URLSafeTimedSerializer(secret)


def _password_fingerprint(user):
    """Short hash of the current password_hash, embedded in reset tokens.

    Once the password changes (including via this same reset link), the
    fingerprint no longer matches, so the old token/link can't be reused.
    """
    return hashlib.sha256((user.password_hash or '').encode('utf-8')).hexdigest()[:16]


FORGOT_PASSWORD_UNIFORM_MESSAGE = (
    'If an account exists for that email address, a verification code has been sent.'
)

RESET_CODE_SALT = 'password-reset-code-salt'
RESET_CODE_MAX_AGE = 3600  # 1 hour


def _hash_reset_code(code: str) -> str:
    return hashlib.sha256((code or '').strip().encode('utf-8')).hexdigest()


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Email a one-time 6-digit code (no URL) — hosting outbound filters often
    reject messages that contain long reset links.
    """
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        user = (
            User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if email
            else None
        )
        if user:
            code = f'{secrets.randbelow(1_000_000):06d}'
            s = get_serializer()
            challenge = s.dumps(
                {
                    'email': user.email,
                    'pf': _password_fingerprint(user),
                    'ch': _hash_reset_code(code),
                },
                salt=RESET_CODE_SALT,
            )
            try:
                from datetime import datetime as _dt

                display_name = (user.full_name or user.username or 'User').strip()
                account_id = (user.username or user.email or '').strip()
                from utils.timezone import format_bd as _format_bd
                requested_at = _format_bd(_dt.utcnow(), '%d %B %Y, %H:%M') + ' (Bangladesh Time)'
                subject = (
                    f"AMS account verification code for {display_name} "
                    f"(username: {account_id})"
                )
                text_body = (
                    f"Dear {display_name},\n\n"
                    "You are receiving this email because an account recovery was requested "
                    "for your account in the Academic Management System (AMS) used by the "
                    "Law Discipline, Khulna University.\n\n"
                    "Account details related to this request:\n"
                    f"- Full name: {display_name}\n"
                    f"- Username: {account_id}\n"
                    f"- Registered email: {user.email}\n"
                    f"- Request time: {requested_at}\n\n"
                    "Purpose of the verification code below:\n"
                    "Enter this code on the AMS account recovery page in your browser "
                    "(the page that opened after you submitted your email). "
                    "The code lets you set a new sign-in password for this account only. "
                    "It is valid for 1 hour from the request time above and works only once. "
                    "After you change your password, or after 1 hour, the code will no longer work.\n\n"
                    f"Your AMS verification code: {code}\n\n"
                    "How to use the code:\n"
                    "1. Keep the AMS recovery page open in your browser "
                    "(or open Forgot Password again and use the same email if needed).\n"
                    "2. Enter the 6-digit code above.\n"
                    "3. Choose a new password and confirm it.\n"
                    "4. Sign in to AMS with your username and the new password.\n\n"
                    "If you did not request this account recovery, please ignore this email. "
                    "Do not share the code. Your existing password will stay the same and no "
                    "change will be made to your account.\n\n"
                    "This message was sent only to the email registered on your AMS account. "
                    "For assistance, contact the Law Discipline office or your AMS administrator.\n\n"
                    "Regards,\n"
                    "Academic Management System\n"
                    "Law Discipline, Khulna University\n"
                    "Sender: recovery@kulawams.xyz\n"
                )
                html_body = (
                    f"<p>Dear {display_name},</p>"
                    "<p>You are receiving this email because an account recovery was requested "
                    "for your account in the Academic Management System (AMS) used by the "
                    "Law Discipline, Khulna University.</p>"
                    "<p><strong>Account details related to this request:</strong></p>"
                    "<ul>"
                    f"<li>Full name: {display_name}</li>"
                    f"<li>Username: {account_id}</li>"
                    f"<li>Registered email: {user.email}</li>"
                    f"<li>Request time: {requested_at}</li>"
                    "</ul>"
                    "<p><strong>Purpose of the verification code below:</strong><br>"
                    "Enter this code on the AMS account recovery page in your browser. "
                    "The code lets you set a new sign-in password for this account only. "
                    "It is valid for <strong>1 hour</strong> and works only once.</p>"
                    f"<p style=\"font-size:1.4rem;letter-spacing:0.2em;\"><strong>"
                    f"{code}</strong></p>"
                    "<p><strong>How to use the code:</strong></p>"
                    "<ol>"
                    "<li>Keep the AMS recovery page open in your browser.</li>"
                    "<li>Enter the 6-digit code above.</li>"
                    "<li>Choose a new password and confirm it.</li>"
                    "<li>Sign in to AMS with your username and the new password.</li>"
                    "</ol>"
                    "<p>If you did not request this account recovery, please ignore this email. "
                    "Do not share the code. Your existing password will stay the same.</p>"
                    "<p>This message was sent only to the email registered on your AMS account. "
                    "For assistance, contact the Law Discipline office or your AMS administrator.</p>"
                    "<p>Regards,<br>"
                    "Academic Management System<br>"
                    "Law Discipline, Khulna University<br>"
                    "Sender: recovery@kulawams.xyz</p>"
                )
                send_recovery_email(
                    subject=subject,
                    recipient=user.email,
                    text_body=text_body,
                    html_body=html_body,
                )
                session['reset_challenge'] = challenge
                session['reset_email_hint'] = user.email
                flash('A verification code has been sent to your email.', 'info')
                return redirect(url_for('auth.verify_reset_code'))
            except Exception as e:
                print('Email send error:', e, file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                current_app.logger.error(f'Password reset email failed: {e}', exc_info=True)
                # Friendly message — full SMTP detail stays in server logs
                err_text = str(e)
                if 'classified as spam' in err_text.lower() or '550' in err_text:
                    flash(
                        'Email recovery could not be completed: the mail host rejected the message '
                        'as spam (outbound content filter). Please ask an AMS administrator to '
                        'reset your password from Admin Dashboard → Users → Reset Password.',
                        'danger',
                    )
                else:
                    flash(
                        'Email recovery failed. Please ask an AMS administrator to reset your password.',
                        'danger',
                    )
        else:
            flash(FORGOT_PASSWORD_UNIFORM_MESSAGE, 'info')
    return render_template('auth/forgot_password.html')


@auth_bp.route('/account/verify-code', methods=['GET', 'POST'])
def verify_reset_code():
    """Enter emailed 6-digit code + new password (no link required in the email)."""
    challenge = session.get('reset_challenge') or request.form.get('challenge') or ''
    email_hint = session.get('reset_email_hint') or ''

    if request.method == 'POST':
        challenge = (request.form.get('challenge') or challenge or '').strip()
        code = (request.form.get('code') or '').strip()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        s = get_serializer()
        try:
            data = s.loads(challenge, salt=RESET_CODE_SALT, max_age=RESET_CODE_MAX_AGE)
        except Exception:
            flash('This recovery session is invalid or has expired. Please request a new code.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        email = data.get('email') if isinstance(data, dict) else None
        token_fingerprint = data.get('pf') if isinstance(data, dict) else None
        code_hash = data.get('ch') if isinstance(data, dict) else None

        user = User.query.filter_by(email=email).first() if email else None
        if not user:
            flash('Invalid user.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        if token_fingerprint is not None and token_fingerprint != _password_fingerprint(user):
            flash('This recovery session is invalid or has expired. Please request a new code.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        if not code or _hash_reset_code(code) != code_hash:
            flash('Invalid verification code. Please check the email and try again.', 'danger')
            return render_template(
                'auth/verify_reset_code.html',
                challenge=challenge,
                email_hint=email or email_hint,
            )

        if not password or not confirm_password:
            flash('Please fill out all fields.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match.', 'danger')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
        else:
            user.set_password(password)
            user.must_change_password = False
            db.session.commit()
            session.pop('reset_challenge', None)
            session.pop('reset_email_hint', None)
            flash('Your password has been updated. Please log in.', 'success')
            return redirect(url_for('auth.login'))

        return render_template(
            'auth/verify_reset_code.html',
            challenge=challenge,
            email_hint=email or email_hint,
        )

    if not challenge:
        flash('Please request a verification code first.', 'info')
        return redirect(url_for('auth.forgot_password'))

    return render_template(
        'auth/verify_reset_code.html',
        challenge=challenge,
        email_hint=email_hint,
    )


@auth_bp.route('/account/access/<token>', methods=['GET', 'POST'])
def account_access(token):
    """Set a new sign-in credential from an emailed one-time link."""
    return _handle_account_access(token)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Legacy URL alias — prefer /account/access/<token> in new emails."""
    return _handle_account_access(token)


def _handle_account_access(token):
    s = get_serializer()
    try:
        data = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('This link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if isinstance(data, dict):
        email = data.get('email')
        token_fingerprint = data.get('pf')
    else:
        # Backward-compat with tokens issued before the fingerprint was added.
        email = data
        token_fingerprint = None

    user = User.query.filter_by(email=email).first() if email else None
    if not user:
        flash('Invalid user.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if token_fingerprint is not None and token_fingerprint != _password_fingerprint(user):
        flash('This link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not password or not confirm_password:
            flash('Please fill out all fields.', 'danger')
        elif password != confirm_password:
            flash('Entries do not match.', 'danger')
        else:
            user.set_password(password)
            user.must_change_password = False
            db.session.commit()
            flash('Your sign-in details were updated. Please log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/account_access.html', token=token)
