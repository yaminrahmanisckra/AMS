"""
Minimal Flask app for Self Assessment only (cPanel / standalone deployment).
Use this as the application entry point when deploying only the Self Assessment module.

In cPanel Python app: set application to "app_self_assessment:create_app" (or "app_self_assessment:app").
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, session
from flask_login import LoginManager, current_user, login_required
from extensions import db, migrate, mail
from user_models import User
from role_utils import ADMIN_ROLE, parse_roles

# Teacher model required for Self Assessment (PsacCommittee, PsacCommitteeMember)
from blueprints.class_management.models import Teacher  # noqa: F401 - needed for FK

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_very_secret_default_key')
    app.config['TEMPLATES_AUTO_RELOAD'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

    # Database
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 1800,
            'pool_size': 5,
            'max_overflow': 5,
            'pool_timeout': 20,
            'connect_args': {'connect_timeout': 5, 'read_timeout': 20, 'write_timeout': 20},
        }
    else:
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(basedir, 'instance', 'academic_management.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Mail (optional – for auth password reset etc.)
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))

    def _env_bool_sa(name, fallback):
        v = os.getenv(name)
        if v is None:
            return fallback
        return str(v).strip().lower() in ('1', 'true', 'yes', 'on')

    app.config['NOTIFICATION_MAIL_SERVER'] = os.getenv('NOTIFICATION_MAIL_SERVER') or app.config['MAIL_SERVER']
    _np = os.getenv('NOTIFICATION_MAIL_PORT')
    app.config['NOTIFICATION_MAIL_PORT'] = int(_np) if _np else app.config['MAIL_PORT']
    app.config['NOTIFICATION_MAIL_USE_TLS'] = _env_bool_sa(
        'NOTIFICATION_MAIL_USE_TLS', app.config['MAIL_USE_TLS']
    )
    app.config['NOTIFICATION_MAIL_USE_SSL'] = _env_bool_sa(
        'NOTIFICATION_MAIL_USE_SSL', app.config['MAIL_USE_SSL']
    )
    app.config['NOTIFICATION_MAIL_USERNAME'] = os.getenv('NOTIFICATION_MAIL_USERNAME')
    app.config['NOTIFICATION_MAIL_PASSWORD'] = os.getenv('NOTIFICATION_MAIL_PASSWORD')
    app.config['NOTIFICATION_MAIL_SENDER'] = os.getenv(
        'NOTIFICATION_MAIL_SENDER', os.getenv('NOTIFICATION_MAIL_USERNAME')
    )
    for k in list(os.environ.keys()):
        if not k.startswith('NOTIFICATION_MAIL_'):
            continue
        val = os.environ.get(k)
        if val is None or str(val).strip() == '':
            continue
        if k.endswith('_PASSWORD'):
            app.config[k] = str(val).rstrip('\r\n')
        else:
            app.config[k] = str(val).strip()

    app.config['DEFAULT_STUDENT_PASSWORD'] = os.getenv('DEFAULT_STUDENT_PASSWORD', 'Student@123')

    mail.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except (ValueError, TypeError):
            return None

    @app.before_request
    def attach_active_role():
        if not current_user.is_authenticated:
            session.pop('active_role', None)
            return
        active_role = session.get('active_role')
        stored_roles = set(parse_roles(current_user.role))
        if active_role:
            if active_role == ADMIN_ROLE and ADMIN_ROLE not in stored_roles:
                active_role = None
            elif active_role != ADMIN_ROLE and active_role not in stored_roles:
                active_role = None
        if not active_role:
            session.pop('active_role', None)
        current_user.active_role = active_role

    @app.template_filter('date')
    def date_format_filter(value, format='%Y'):
        if value == 'now':
            return datetime.utcnow().strftime(format)
        return value

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    # Blueprints: Auth (login) + Self Assessment only
    from blueprints.auth.routes import auth_bp
    from blueprints.self_assessment import self_assessment_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(self_assessment_bp, url_prefix='/self-assessment')

    # Root: redirect to Self Assessment if logged in, else login
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('self_assessment.index'))
        return redirect(url_for('auth.login'))

    # Head dashboard: redirect to Self Assessment (so /head/dashboard links don’t 500)
    @app.route('/head/dashboard')
    @login_required
    def head_dashboard():
        return redirect(url_for('self_assessment.index'))

    return app


app = create_app()
