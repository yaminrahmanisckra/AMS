import hashlib
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
    'If an account exists for that email address, a password reset link has been sent.'
)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        # Case-insensitive + trimmed match (DB email may differ in case/whitespace)
        user = (
            User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if email
            else None
        )
        if user:
            s = get_serializer()
            token = s.dumps(
                {'email': user.email, 'pf': _password_fingerprint(user)},
                salt='password-reset-salt',
            )
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                from datetime import datetime as _dt

                display_name = (user.full_name or user.username or 'User').strip()
                account_id = (user.username or user.email or '').strip()
                requested_at = _dt.utcnow().strftime('%d %B %Y, %H:%M UTC')
                # Keep subject/body short — hosting outbound filters flag long
                # "password reset / click here / security" templates as spam (550).
                subject = f"AMS account help — {account_id} — Law Discipline, KU"
                text_body = (
                    f"Dear {display_name},\n\n"
                    "Law Discipline, Khulna University (Academic Management System).\n\n"
                    f"Account: {account_id}\n"
                    f"Email: {user.email}\n"
                    f"Time: {requested_at}\n\n"
                    "Open this AMS page to choose a new sign-in password "
                    "(valid for 1 hour, one use):\n"
                    f"{reset_url}\n\n"
                    "If you did not ask for this, ignore this message. "
                    "Your current password stays unchanged.\n\n"
                    "Academic Management System\n"
                    "Law Discipline, Khulna University\n"
                )
                # Plain text only — HTML + multiple CTAs often trip cPanel spam filters
                send_recovery_email(
                    subject=subject,
                    recipient=user.email,
                    text_body=text_body,
                    html_body=None,
                )
                flash('A password reset link has been sent to your email.', 'info')
            except Exception as e:
                print('Email send error:', e, file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                current_app.logger.error(f'Password reset email failed: {e}', exc_info=True)
                # Show SMTP reason while hosting spam-filter issues are being fixed
                flash(f'Failed to send email: {e}', 'danger')
        else:
            # Do not reveal whether the email is registered
            flash(FORGOT_PASSWORD_UNIFORM_MESSAGE, 'info')
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = get_serializer()
    try:
        data = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'danger')
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
        # Password already changed since this link was issued (or link was reused) — dead link.
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not password or not confirm_password:
            flash('Please fill out all fields.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match.', 'danger')
        else:
            user.set_password(password)
            user.must_change_password = False
            db.session.commit()
            flash('Your password has been reset. Please login.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)
