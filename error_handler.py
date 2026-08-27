"""Central application logging and HTTP error handlers.

Log files (one directory, shared handlers):
  ams_all.log         — INFO+ from the whole app (single place to read)
  ams_errors.log      — WARNING+ and exceptions
  ams_data_events.log — silent data-loss risks / destructive data ops
  detailed_errors.log — human-readable exception dumps
"""
import html
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import has_request_context, jsonify, request
from werkzeug.exceptions import HTTPException

_LOGGING_CONFIGURED = False
_LOG_DIR = None

# Shared format for rotating files
_FILE_FORMAT = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)


def _log_dir():
    """Prefer a private log directory outside the web-served tree when configured."""
    global _LOG_DIR
    if _LOG_DIR:
        return _LOG_DIR
    configured = os.environ.get('AMS_LOG_DIR', '').strip()
    candidates = []
    if configured:
        candidates.append(configured)
    base = os.path.dirname(os.path.abspath(__file__))
    sibling = os.path.join(os.path.dirname(base), 'ams_logs')
    candidates.append(sibling)
    candidates.append(os.path.join(base, 'logs'))

    last_error = None
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, '.ams_log_write_test')
            with open(probe, 'w', encoding='utf-8') as handle:
                handle.write('ok')
            os.remove(probe)
            _LOG_DIR = path
            return path
        except OSError as exc:
            last_error = exc
            continue
    raise OSError(f'Unable to create writable AMS log directory; last error: {last_error}')


def get_log_paths():
    """Return absolute paths of the central log files."""
    log_dir = _log_dir()
    return {
        'dir': log_dir,
        'all': os.path.join(log_dir, 'ams_all.log'),
        'errors': os.path.join(log_dir, 'ams_errors.log'),
        'data_events': os.path.join(log_dir, 'ams_data_events.log'),
        'detailed_errors': os.path.join(log_dir, 'detailed_errors.log'),
        # Legacy alias (same as errors for older docs/scripts)
        'app_errors': os.path.join(log_dir, 'ams_errors.log'),
    }


def _rotating_handler(path, level, max_bytes=5 * 1024 * 1024, backups=10):
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding='utf-8')
    handler.setLevel(level)
    handler.setFormatter(_FILE_FORMAT)
    return handler


def _request_context_dict():
    if not has_request_context():
        return {}
    ctx = {
        'url': request.url,
        'path': request.path,
        'method': request.method,
        'endpoint': request.endpoint,
        'remote_addr': request.headers.get('X-Forwarded-For', request.remote_addr),
    }
    try:
        from flask_login import current_user
        if current_user and getattr(current_user, 'is_authenticated', False):
            ctx['user_id'] = getattr(current_user, 'id', None)
            ctx['username'] = getattr(current_user, 'username', None)
    except Exception:
        pass
    return ctx


def setup_error_logging():
    """
    Backward-compatible entry: configure central loggers if needed.
    Prefer setup_application_logging(app) at app startup.
    """
    _configure_central_logging(app=None)
    return logging.getLogger('ams_errors')


def setup_application_logging(app=None):
    """Wire Flask + root loggers into one log directory (all / errors / data)."""
    paths = _configure_central_logging(app=app)
    if app is not None:
        app.logger.info(
            'Central logging ready: dir=%s files=ams_all.log,ams_errors.log,ams_data_events.log',
            paths['dir'],
        )
    return paths


def _configure_central_logging(app=None):
    global _LOGGING_CONFIGURED
    paths = get_log_paths()

    if _LOGGING_CONFIGURED:
        if app is not None:
            _attach_flask_logger(app, paths)
        return paths

    all_handler = _rotating_handler(paths['all'], logging.INFO)
    error_handler = _rotating_handler(paths['errors'], logging.WARNING)
    data_handler = _rotating_handler(paths['data_events'], logging.INFO)
    # Legacy filename symlink-style duplicate for older deploy docs
    legacy_errors = os.path.join(paths['dir'], 'app_errors.log')
    if legacy_errors != paths['errors']:
        legacy_handler = _rotating_handler(legacy_errors, logging.WARNING)
    else:
        legacy_handler = None

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(logging.WARNING)
    stream.setFormatter(_FILE_FORMAT)

    # Dedicated loggers
    for name, level, extra_handlers in (
        ('ams_errors', logging.INFO, []),
        ('ams_data', logging.INFO, [data_handler]),
        ('ams', logging.INFO, []),
    ):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        if not logger.handlers:
            logger.addHandler(all_handler)
            logger.addHandler(error_handler)
            if legacy_handler is not None:
                logger.addHandler(legacy_handler)
            for h in extra_handlers:
                logger.addHandler(h)
            logger.addHandler(stream)

    # Root: capture third-party + unconfigured loggers into ams_all / ams_errors
    root = logging.getLogger()
    if not any(getattr(h, '_ams_central', False) for h in root.handlers):
        for h in (all_handler, error_handler):
            h._ams_central = True  # type: ignore[attr-defined]
            root.addHandler(h)
        root.setLevel(logging.INFO)

    # Quiet noisy libraries in the shared file (still WARNING+)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)

    if app is not None:
        _attach_flask_logger(app, paths)

    _LOGGING_CONFIGURED = True
    return paths


def _attach_flask_logger(app, paths):
    """Ensure app.logger reaches central files via root (no duplicate handlers)."""
    # Production used to clamp to WARNING; keep INFO so data/audit events land in ams_all.
    app.logger.setLevel(logging.INFO)
    # Remove previous AMS file handlers only (keep any StreamHandler Flask added)
    kept = []
    for h in list(app.logger.handlers):
        if getattr(h, '_ams_central', False):
            app.logger.removeHandler(h)
        else:
            kept.append(h)
    app.logger.propagate = True
    # Quiet default Flask stream noise is fine; files come from root handlers.
    _ = (paths, kept)


def log_data_event(event_type, message, level='WARNING', **context):
    """
    Log a data-integrity / silent-loss related event to ams_data_events.log
    (and ams_all / ams_errors according to level).

    event_type examples:
      AUTO_SAVE_PRESERVE, AUTO_SAVE_CLEAR, ASSESSMENT_CLEAR,
      CLASS_STUDENT_DELETE, SESSION_DEDUPE_MERGE, SESSION_DEDUPE_ARCHIVE
    """
    _configure_central_logging()
    logger = logging.getLogger('ams_data')
    payload = {
        'event': event_type,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'request': _request_context_dict(),
        'context': {k: v for k, v in context.items() if v is not None},
    }
    try:
        line = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        line = f'{event_type}: {message} | {context}'

    level_name = (level or 'WARNING').upper()
    log_fn = getattr(logger, level_name.lower(), logger.warning)
    log_fn('%s | %s', event_type, line)
    return payload


def class_student_mark_snapshot(class_student):
    """Compact mark snapshot for data-event logs (no huge payloads)."""
    if not class_student:
        return None
    snap = {
        'row_id': getattr(class_student, 'id', None),
        'student_id': getattr(class_student, 'student_id', None),
        'session_id': getattr(class_student, 'session_id', None),
    }
    for field in (
        'assessment1', 'assessment2', 'assessment3', 'assessment4',
        'assessment_total', 'assessment_total_40',
        'sessional_report', 'sessional_viva',
    ):
        val = getattr(class_student, field, None)
        if val is not None:
            snap[field] = val
    absent = getattr(class_student, 'assessment_absent', None)
    if absent:
        snap['assessment_absent'] = absent
    return snap


def class_student_has_marks(class_student):
    if not class_student:
        return False
    for field in (
        'assessment1', 'assessment2', 'assessment3', 'assessment4',
        'assessment_total', 'assessment_total_40',
        'sessional_report', 'sessional_viva',
    ):
        if getattr(class_student, field, None) is not None:
            return True
    return bool(getattr(class_student, 'assessment_absent', None))


def log_error(error, context=None):
    """Log detailed error information to the private log only."""
    _configure_central_logging()
    logger = logging.getLogger('ams_errors')

    error_info = {
        'timestamp': datetime.now().isoformat(),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'request': _request_context_dict(),
        'context': context or {},
    }

    logger.error('Application Error: %s', error_info)

    error_file = get_log_paths()['detailed_errors']
    try:
        with open(error_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"ERROR at {error_info['timestamp']}\n")
            f.write(f"URL: {error_info['request'].get('url', 'No request')}\n")
            f.write(f"Method: {error_info['request'].get('method', 'No request')}\n")
            f.write(f"User: {error_info['request'].get('username', '-')}\n")
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
        'log_paths': get_log_paths(),
        'environment_variables': {
            'FLASK_ENV': os.environ.get('FLASK_ENV'),
            'CPANEL': os.environ.get('CPANEL'),
            'RENDER': os.environ.get('RENDER'),
            'AMS_LOG_DIR': os.environ.get('AMS_LOG_DIR'),
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
        if error.code and error.code >= 400:
            if error.code >= 500:
                return create_error_response(error, error.code)
            return create_error_response(error, error.code)
        return create_error_response(error, 500)

    @app.errorhandler(Exception)
    def handle_exception(error):
        if isinstance(error, HTTPException):
            return handle_http_exception(error)
        return create_error_response(error, 500)
