"""Central application logging and HTTP error handlers.

Log files (one directory):
  ams_all.log         — app/audit INFO+ from AMS loggers only (not every library)
  ams_errors.log      — WARNING+ and exceptions
  ams_data_events.log — silent data-loss risks / destructive data ops
  detailed_errors.log — human-readable exception dumps
  app_errors.log      — legacy alias of ams_errors.log content

Production-safe: setup never crashes the app; root stays at WARNING to avoid
slow page loads from flooding shared-hosting disks.
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
_SETUP_ERROR = None

_FILE_FORMAT = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)


def _log_dir():
    """Resolve a writable log directory without crashing the app."""
    global _LOG_DIR, _SETUP_ERROR
    if _LOG_DIR:
        return _LOG_DIR

    configured = os.environ.get('AMS_LOG_DIR', '').strip()
    base = os.path.dirname(os.path.abspath(__file__))
    # Prefer in-app logs/ first (fast, always under the app tree), then private sibling.
    candidates = []
    if configured:
        candidates.append(configured)
    candidates.append(os.path.join(base, 'logs'))
    candidates.append(os.path.join(os.path.dirname(base), 'ams_logs'))
    home = os.path.expanduser('~')
    if home and home != '~':
        candidates.append(os.path.join(home, 'ams_logs'))

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

    _SETUP_ERROR = last_error
    # Last resort: still return in-app logs path (handlers may fail soft later)
    fallback = os.path.join(base, 'logs')
    try:
        os.makedirs(fallback, exist_ok=True)
    except OSError:
        pass
    _LOG_DIR = fallback
    return fallback


def get_log_paths():
    """Return absolute paths of the central log files."""
    log_dir = _log_dir()
    errors = os.path.join(log_dir, 'ams_errors.log')
    return {
        'dir': log_dir,
        'all': os.path.join(log_dir, 'ams_all.log'),
        'errors': errors,
        'data_events': os.path.join(log_dir, 'ams_data_events.log'),
        'detailed_errors': os.path.join(log_dir, 'detailed_errors.log'),
        'app_errors': os.path.join(log_dir, 'app_errors.log'),
    }


def _rotating_handler(path, level, max_bytes=5 * 1024 * 1024, backups=5):
    handler = RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backups, encoding='utf-8', delay=True
    )
    handler.setLevel(level)
    handler.setFormatter(_FILE_FORMAT)
    handler._ams_central = True  # type: ignore[attr-defined]
    return handler


def _request_context_dict():
    if not has_request_context():
        return {}
    ctx = {
        'url': getattr(request, 'url', None),
        'path': getattr(request, 'path', None),
        'method': getattr(request, 'method', None),
        'endpoint': getattr(request, 'endpoint', None),
        'remote_addr': request.headers.get('X-Forwarded-For', request.remote_addr)
        if request else None,
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
    """Backward-compatible entry."""
    _configure_central_logging(app=None)
    return logging.getLogger('ams_errors')


def setup_application_logging(app=None):
    """Wire AMS loggers; never raise — site must still boot if disk logging fails."""
    try:
        paths = _configure_central_logging(app=app)
        if app is not None:
            # Production: keep app.logger quiet to avoid slow shared-hosting I/O.
            import os as _os
            if _os.getenv('FLASK_ENV') == 'production' or _os.getenv('CPANEL'):
                app.logger.setLevel(logging.WARNING)
            else:
                app.logger.setLevel(logging.INFO)
            app.logger.warning(
                'Central logging ready: dir=%s (all/errors/data_events)',
                paths.get('dir'),
            )
        return paths
    except Exception as exc:
        global _SETUP_ERROR
        _SETUP_ERROR = exc
        try:
            sys.stderr.write(f'[AMS] logging setup failed (non-fatal): {exc}\n')
        except Exception:
            pass
        return {}


def _configure_central_logging(app=None):
    global _LOGGING_CONFIGURED
    paths = get_log_paths()

    if _LOGGING_CONFIGURED:
        if app is not None:
            _attach_flask_logger(app)
        return paths

    try:
        all_handler = _rotating_handler(paths['all'], logging.INFO)
        error_handler = _rotating_handler(paths['errors'], logging.WARNING)
        data_handler = _rotating_handler(paths['data_events'], logging.INFO)
        legacy_handler = _rotating_handler(paths['app_errors'], logging.WARNING)
    except Exception as exc:
        # Cannot open log files — leave stdout-only and continue.
        global _SETUP_ERROR
        _SETUP_ERROR = exc
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(logging.WARNING)
        stream.setFormatter(_FILE_FORMAT)
        for name in ('ams_errors', 'ams_data', 'ams'):
            lg = logging.getLogger(name)
            lg.setLevel(logging.INFO)
            lg.propagate = False
            if not lg.handlers:
                lg.addHandler(stream)
        _LOGGING_CONFIGURED = True
        return paths

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(logging.WARNING)
    stream.setFormatter(_FILE_FORMAT)

    # Dedicated AMS loggers only — do NOT put INFO on root (that flooded disk / slowed pages).
    for name, handlers in (
        ('ams_errors', (all_handler, error_handler, legacy_handler, stream)),
        ('ams_data', (all_handler, error_handler, legacy_handler, data_handler, stream)),
        ('ams', (all_handler, error_handler, legacy_handler, stream)),
    ):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            for handler in handlers:
                logger.addHandler(handler)

    # Root: WARNING+ only → errors file (uncaught library warnings), no INFO spam
    root = logging.getLogger()
    if not any(getattr(h, '_ams_central', False) for h in root.handlers):
        root.addHandler(error_handler)
        root.addHandler(legacy_handler)
        # Keep existing root level if already higher; otherwise WARNING for production safety
        if root.level == logging.NOTSET or root.level < logging.WARNING:
            if os.getenv('FLASK_ENV') == 'production' or os.getenv('CPANEL'):
                root.setLevel(logging.WARNING)
            else:
                root.setLevel(logging.INFO)
                root.addHandler(all_handler)

    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    if app is not None:
        _attach_flask_logger(app)

    _LOGGING_CONFIGURED = True
    return paths


def _attach_flask_logger(app):
    """Route Flask logger through root; remove duplicate AMS file handlers."""
    for h in list(app.logger.handlers):
        if getattr(h, '_ams_central', False):
            app.logger.removeHandler(h)
    app.logger.propagate = True


def log_data_event(event_type, message, level='WARNING', **context):
    """
    Log a data-integrity / silent-loss related event.

    event_type examples:
      AUTO_SAVE_PRESERVE, AUTO_SAVE_CLEAR, ASSESSMENT_CLEAR,
      CLASS_STUDENT_DELETE, SESSION_DEDUPE_MERGE, SESSION_DEDUPE_ARCHIVE
    """
    try:
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
    except Exception:
        # Never break a request because logging failed
        return None


def class_student_mark_snapshot(class_student):
    """Compact mark snapshot for data-event logs."""
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
    try:
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
    except Exception:
        try:
            sys.stderr.write(f'[AMS] log_error failed for: {error}\n')
        except Exception:
            pass


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
        'logging_setup_error': str(_SETUP_ERROR) if _SETUP_ERROR else None,
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
