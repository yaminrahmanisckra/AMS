from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from user_models import User
from extensions import db
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from flask_mail import Message
from extensions import mail
import traceback
import sys
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

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    default_login_role = 'teacher'
    selected_role = default_login_role
    student_default_password = current_app.config.get('DEFAULT_STUDENT_PASSWORD', 'Student@123')
    
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
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
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
        current_app.logger.info(f"Successfully logged in user: {user.username} (ID: {user.id}) with role: {selected_role}")
        flash('Login successful!', 'success')
        
        # Create response and ensure session cookie is properly set
        response = redirect(url_for('index'))
        # Force session to be saved
        session.permanent = False
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

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()  # Clear all session data
    flash('You have been logged out.', 'info')
    response = redirect(url_for('auth.login'))
    # Delete Flask session cookie and Flask-Login remember cookie
    response.set_cookie('session', '', expires=0, path='/')
    response.set_cookie('remember_token', '', expires=0, path='/')
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

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            s = get_serializer()
            token = s.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                subject = "Password Reset Request - Academic Management System"
                html_body = f"""
                <html>
                <body>
                    <h2>Password Reset Request</h2>
                    <p>Hello,</p>
                    <p>You have requested to reset your password for the Academic Management System.</p>
                    <p>Click the link below to reset your password:</p>
                    <p><a href=\"{reset_url}\" style=\"background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;\">Reset Password</a></p>
                    <p>Or copy and paste this URL in your browser:</p>
                    <p>{reset_url}</p>
                    <p>This link will expire in 1 hour.</p>
                    <p>If you did not request this password reset, please ignore this email.</p>
                    <br>
                    <p>Best regards,</p>
                    <p>Academic Management System Team</p>
                </body>
                </html>
                """
                text_body = f"""
                Password Reset Request
                
                Hello,
                
                You have requested to reset your password for the Academic Management System.
                
                Click the link below to reset your password:
                {reset_url}
                
                This link will expire in 1 hour.
                
                If you did not request this password reset, please ignore this email.
                
                Best regards,
                Academic Management System Team
                """
                msg = Message(
                    subject=subject,
                    recipients=[user.email],
                    html=html_body,
                    body=text_body
                )
                print("Trying to send email...", file=sys.stderr)
                mail.send(msg)
                print("Email sent successfully!", file=sys.stderr)
                flash('A password reset link has been sent to your email.', 'info')
            except Exception as e:
                print('Email send error:', e, file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                flash('Failed to send email. Please try again later.', 'danger')
        else:
            flash('No user found with that email.', 'danger')
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid user.', 'danger')
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
            db.session.commit()
            flash('Your password has been reset. Please login.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)
    s = get_serializer()
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid user.', 'danger')
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
            db.session.commit()
            flash('Your password has been reset. Please login.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token) 