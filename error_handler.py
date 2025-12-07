import os
import sys
import traceback
from datetime import datetime
from flask import current_app, request, jsonify
import logging

# Configure logging for cPanel
def setup_error_logging():
    """Setup comprehensive error logging for cPanel deployment"""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure file logging
    log_file = os.path.join(log_dir, 'app_errors.log')
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def log_error(error, context=None):
    """Log detailed error information"""
    logger = setup_error_logging()
    
    error_info = {
        'timestamp': datetime.now().isoformat(),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'request_url': request.url if request else 'No request',
        'request_method': request.method if request else 'No request',
        'user_agent': request.headers.get('User-Agent') if request else 'No request',
        'context': context or {}
    }
    
    logger.error(f"Application Error: {error_info}")
    
    # Also write to a separate error file for easy access
    error_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'detailed_errors.log')
    with open(error_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"ERROR at {error_info['timestamp']}\n")
        f.write(f"URL: {error_info['request_url']}\n")
        f.write(f"Method: {error_info['request_method']}\n")
        f.write(f"Error Type: {error_info['error_type']}\n")
        f.write(f"Error Message: {error_info['error_message']}\n")
        f.write(f"Context: {error_info['context']}\n")
        f.write(f"Traceback:\n{error_info['traceback']}\n")
        f.write(f"{'='*80}\n")

def check_dependencies():
    """Check if all required dependencies are available"""
    logger = setup_error_logging()
    
    dependencies = {
        'pandas': 'pandas',
        'openpyxl': 'openpyxl', 
        'reportlab': 'reportlab',
        'python-docx': 'docx',
        'Pillow': 'PIL',
        'numpy': 'numpy'
    }
    
    missing_deps = []
    available_deps = {}
    
    for dep_name, import_name in dependencies.items():
        try:
            module = __import__(import_name)
            available_deps[dep_name] = module.__version__ if hasattr(module, '__version__') else 'Available'
            logger.info(f"✓ {dep_name}: {available_deps[dep_name]}")
        except ImportError as e:
            missing_deps.append(dep_name)
            logger.error(f"✗ {dep_name}: Missing - {e}")
    
    return {
        'available': available_deps,
        'missing': missing_deps,
        'all_available': len(missing_deps) == 0
    }

def check_file_permissions():
    """Check file and directory permissions"""
    logger = setup_error_logging()
    
    paths_to_check = [
        'uploads',
        'logs',
        'instance',
        'static',
        'templates'
    ]
    
    permission_issues = []
    
    for path in paths_to_check:
        if os.path.exists(path):
            try:
                # Check if directory is writable
                test_file = os.path.join(path, '.test_write')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info(f"✓ {path}: Writable")
            except Exception as e:
                permission_issues.append(f"{path}: {str(e)}")
                logger.error(f"✗ {path}: Permission issue - {e}")
        else:
            try:
                os.makedirs(path, exist_ok=True)
                logger.info(f"✓ {path}: Created")
            except Exception as e:
                permission_issues.append(f"{path}: Cannot create - {str(e)}")
                logger.error(f"✗ {path}: Cannot create - {e}")
    
    return permission_issues

def get_system_info():
    """Get system information for debugging"""
    import platform
    
    return {
        'python_version': sys.version,
        'platform': platform.platform(),
        'architecture': platform.architecture(),
        'processor': platform.processor(),
        'current_working_directory': os.getcwd(),
        'environment_variables': {
            'FLASK_ENV': os.environ.get('FLASK_ENV'),
            'CPANEL': os.environ.get('CPANEL'),
            'RENDER': os.environ.get('RENDER'),
            'DATABASE_URL': '***HIDDEN***' if os.environ.get('DATABASE_URL') else None
        }
    }

def create_error_response(error, status_code=500):
    """Create a standardized error response"""
    error_info = {
        'error': str(error),
        'type': type(error).__name__,
        'timestamp': datetime.now().isoformat(),
        'path': request.path if request else 'Unknown',
        'method': request.method if request else 'Unknown'
    }
    
    # Log the error
    log_error(error, {'status_code': status_code})
    
    # Return JSON response for API calls, HTML for others
    if request and request.path.startswith('/api/'):
        return jsonify(error_info), status_code
    else:
        return f"""
        <html>
        <head><title>Error {status_code}</title></head>
        <body>
            <h1>Error {status_code}</h1>
            <p><strong>Error:</strong> {error}</p>
            <p><strong>Type:</strong> {type(error).__name__}</p>
            <p><strong>Time:</strong> {error_info['timestamp']}</p>
            <p><strong>Path:</strong> {error_info['path']}</p>
            <hr>
            <p>Please check the error logs for more details.</p>
        </body>
        </html>
        """, status_code

# Global exception handler for Flask app
def register_error_handlers(app):
    """Register error handlers for the Flask application"""
    
    @app.errorhandler(500)
    def internal_error(error):
        return create_error_response(error, 500)
    
    @app.errorhandler(404)
    def not_found_error(error):
        return create_error_response(error, 404)
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        return create_error_response(error, 500)
    
    # Add before_request to log all requests
    @app.before_request
    def log_request():
        if current_app:
            current_app.logger.info(f"Request: {request.method} {request.url}")
    
    # Add after_request to log responses
    @app.after_request
    def log_response(response):
        if current_app:
            current_app.logger.info(f"Response: {response.status_code} for {request.method} {request.url}")
        return response 