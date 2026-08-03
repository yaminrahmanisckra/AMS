import html
import logging
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException


def _log_dir():
    """Prefer a private log directory outside the web-served tree when configured."""
    configured = os.environ.get('AMS_LOG_DIR', '').strip()
    if configured:
        path = configured
    else:
        # Parent of docroot: .../ams_logs next to the site folder when possible
        base = os.path.dirname(os.path.abspath(__file__))
        sibling = os.path.join(os.path.dirname(base), 'ams_logs')
        path = sibling if os.path.isdir(os.path.dirname(base)) else os.path.join(base, 'logs')
    os.makedirs(path, exist_ok=True)
    return path


def setup_error_logging():
    """Setup rotating file logging (not into a publicly served path when AMS_LOG_DIR is set)."""
    log_dir = _log_dir()
    log_file = os.path.join(log_dir, 'app_errors.log')

    logger = logging.getLogger('ams_errors')
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(logging.WARNING)
        logger.addHandler(stream)
    return logger


def log_error(error, context=None):
    """Log detailed error information to the private log only."""
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

    logger.error('Application Error: %s', error_info)

    error_file = os.path.join(_log_dir(), 'detailed_errors.log')
    try:
        with open(error_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"ERROR at {error_info['timestamp']}\n")
            f.write(f"URL: {error_info['request_url']}\n")
            f.write(f"Method: {error_info['request_method']}\n")
            f.write(f"Error Type: {error_info['error_type']}\n")
            f.write(f"Error Message: {error_info['error_message']}\n")
            f.write(f"Context: {error_info['context']}\n")
            f.write(f"Traceback:\n{error_info['traceback']}\n")
            f.write(f"{'=' * 80}\n")
    except OSError:
        logger.error('Failed to append detailed_errors.log', exc_info=True)


def check_dependencies():
    """Check if all required dependencies are available"""
    logger = setup_error_logging()

    dependencies = {
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'reportlab': 'reportlab',
        'python-docx': 'docx',
        'Pillow': 'PIL',
        'numpy': 'numpy',
        'weasyprint': 'weasyprint'
    }

    missing_deps = []
    available_deps = {}

    for dep_name, import_name in dependencies.items():
        try:
            module = __import__(import_name)
            available_deps[dep_name] = module.__version__ if hasattr(module, '__version__') else 'Available'
            logger.info('✓ %s: %s', dep_name, available_deps[dep_name])
        except ImportError as e:
            missing_deps.append(dep_name)
            logger.error('✗ %s: Missing - %s', dep_name, e)

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
                test_file = os.path.join(path, '.test_write')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info('✓ %s: Writable', path)
            except Exception as e:
                permission_issues.append(f'{path}: {str(e)}')
                logger.error('✗ %s: Permission issue - %s', path, e)
        else:
            try:
                os.makedirs(path, exist_ok=True)
                logger.info('✓ %s: Created', path)
            except Exception as e:
                permission_issues.append(f'{path}: Cannot create - {str(e)}')
                logger.error('✗ %s: Cannot create - %s', path, e)

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
    """Create a redacted error response (no exception text or raw path reflection)."""
    safe_path = html.escape(request.path if request else 'Unknown')
    timestamp = datetime.now().isoformat()

    log_error(error, {'status_code': status_code})

    public = {
        'error': 'An unexpected error occurred.' if status_code >= 500 else 'The requested resource was not found.' if status_code == 404 else 'Request could not be completed.',
        'status': status_code,
        'timestamp': timestamp,
    }

    if request and (
        request.path.startswith('/api/')
        or request.accept_mimetypes.best == 'application/json'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    ):
        return jsonify(public), status_code

    title = html.escape(f'Error {status_code}')
    message = html.escape(public['error'])
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <h1>{title}</h1>
  <p>{message}</p>
  <p>Time: {html.escape(timestamp)}</p>
  <p>Reference path: {safe_path}</p>
  <hr>
  <p>If this persists, contact the system administrator. Details are recorded in the private application log.</p>
</body>
</html>
""", status_code


def register_error_handlers(app):
    """Register error handlers for the Flask application"""

    @app.errorhandler(500)
    def internal_error(error):
        return create_error_response(error, 500)

    @app.errorhandler(404)
    def not_found_error(error):
        return create_error_response(error, 404)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        # Preserve abort(403)/405/etc. status codes (do not collapse to 500)
        if error.code and error.code >= 400:
            if error.code >= 500:
                return create_error_response(error, error.code)
            # Client errors: redacted generic page without leaking description HTML oddly
            return create_error_response(error, error.code)
        return create_error_response(error, 500)

    @app.errorhandler(Exception)
    def handle_exception(error):
        if isinstance(error, HTTPException):
            return handle_http_exception(error)
        return create_error_response(error, 500)
