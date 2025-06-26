import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, current_user, login_required
from extensions import db, migrate
from user_models import User

load_dotenv()

def create_app():
    app = Flask(__name__)

    @app.template_filter('date')
    def date_format_filter(value, format='%Y'):
        if value == 'now':
            return datetime.utcnow().strftime(format)
        return value

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_very_secret_default_key')
    app.config['TEMPLATES_AUTO_RELOAD'] = False
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000

    # Database configuration for different environments
    if os.environ.get('RENDER'):
        # Render deployment
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_size': 10,
                'pool_recycle': 300,
                'pool_pre_ping': True
            }
        else:
            db_path = os.path.join(app.instance_path, 'academic_management.db')
            os.makedirs(app.instance_path, exist_ok=True)
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    elif os.environ.get('CPANEL'):
        # cPanel deployment
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        else:
            # Fallback to SQLite for cPanel
            db_path = os.path.join(app.instance_path, 'academic_management.db')
            os.makedirs(app.instance_path, exist_ok=True)
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    else:
        # Local development - always use SQLite
        db_path = os.path.join(app.instance_path, 'academic_management.db')
        os.makedirs(app.instance_path, exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login' 
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from blueprints.class_management.routes import class_management_bp
    from blueprints.result_management.routes import result_management_bp
    from blueprints.routine_management.routes import routine_management_bp
    from blueprints.auth.routes import auth_bp

    app.register_blueprint(class_management_bp, url_prefix='/class-management')
    app.register_blueprint(result_management_bp, url_prefix='/result-management')
    app.register_blueprint(routine_management_bp, url_prefix='/routine-management')
    app.register_blueprint(auth_bp)

    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))

        return render_template('dashboard.html')

    @app.route('/test-form', methods=['GET', 'POST'])
    def test_form():
        test_result = None
        if request.method == 'POST':
            test_result = {
                'name': request.form.get('test_name'),
                'email': request.form.get('test_email'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            flash('Test form submitted successfully!', 'success')
        return render_template('test_form.html', test_result=test_result)

    @app.route('/simple-test', methods=['GET', 'POST'])
    def simple_test():
        result = None
        if request.method == 'POST':
            result = f"Name: {request.form.get('test_name')}, Email: {request.form.get('test_email')}"
        return render_template('simple_test.html', result=result)

    @app.route('/admin')
    @login_required
    def admin_dashboard():
        if not current_user.role == 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        users = User.query.all()
        return render_template('admin_dashboard.html', users=users)

    @app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
    @login_required
    def delete_user(user_id):
        if not current_user.role == 'admin':
            flash('You do not have permission to perform this action.', 'danger')
            return redirect(url_for('index'))
        
        user_to_delete = User.query.get_or_404(user_id)
        if user_to_delete.role == 'admin':
            flash('Admin users cannot be deleted.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('User deleted successfully.', 'success')
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    def admin_edit_user(user_id):
        if not current_user.role == 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        
        user_to_edit = User.query.get_or_404(user_id)
        if user_to_edit.role == 'admin':
            flash('Cannot edit admin users from here.', 'danger')
            return redirect(url_for('admin_dashboard'))

        if request.method == 'POST':
            user_to_edit.full_name = request.form['full_name']
            user_to_edit.email = request.form['email']
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        
        return render_template('admin_edit_user.html', user=user_to_edit)

    @app.route('/admin/reset_password/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    def admin_reset_password(user_id):
        if not current_user.role == 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))

        user_to_reset = User.query.get_or_404(user_id)
        if user_to_reset.role == 'admin':
            flash('Cannot reset password for admin users from here.', 'danger')
            return redirect(url_for('admin_dashboard'))

        if request.method == 'POST':
            new_password = request.form['new_password']
            user_to_reset.set_password(new_password)
            db.session.commit()
            flash(f"Password for {user_to_reset.username} has been reset.", 'success')
            return redirect(url_for('admin_dashboard'))
            
        return render_template('admin_reset_password.html', user=user_to_reset)

    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Get port from environment variable (for Render) or use default
    port = int(os.environ.get('PORT', 5001))
    
    # Use 0.0.0.0 for production (Render) and 127.0.0.1 for development
    host = '0.0.0.0' if os.environ.get('RENDER') else '127.0.0.1'
    
    app.run(host=host, port=port) 