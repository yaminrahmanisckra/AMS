"""LOG-01: do not send unexpected exception text to the browser."""
import importlib.util
from pathlib import Path

from flask import get_flashed_messages

from error_handler import create_error_response
from utils.public_errors import api_error, flash_exception, report_exception

_CHECKER = Path(__file__).resolve().parents[1] / 'scripts/security/check_client_exceptions.py'
_spec = importlib.util.spec_from_file_location('check_client_exceptions', _CHECKER)
_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checker)


SECRET = 'OperationalError: Table \'kulawams.users\' doesn\'t exist [/home/secret/app.py]'


def test_api_error_hides_exception_text(app):
    with app.test_request_context('/'):
        response, status = api_error(RuntimeError(SECRET), 'Could not save.')
        data = response.get_json()
    assert status == 500
    blob = ' '.join(str(v) for v in data.values())
    assert 'OperationalError' not in blob
    assert 'kulawams.users' not in blob
    assert '/home/secret' not in blob
    assert data['error_id']
    assert data['error_id'] in data['message']
    assert data['success'] is False


def test_flash_exception_hides_exception_text(app):
    with app.test_request_context('/'):
        text = flash_exception(RuntimeError(SECRET), 'Could not create the session.', 'error')
        messages = get_flashed_messages(with_categories=True)
    assert SECRET not in text
    assert 'ref:' in text
    assert messages
    assert SECRET not in messages[0][1]


def test_report_exception_returns_correlation_id(app):
    with app.test_request_context('/'):
        error_id, text = report_exception(ValueError(SECRET))
    assert error_id
    assert error_id in text
    assert SECRET not in text


def test_create_error_response_includes_error_id(app):
    with app.test_request_context('/api/demo', headers={'X-Requested-With': 'XMLHttpRequest'}):
        response, status = create_error_response(RuntimeError(SECRET), 500)
        data = response.get_json()
    assert status == 500
    assert data['error_id']
    assert SECRET not in data['error']
    assert SECRET not in data['message']


def test_favicon_is_served_and_not_logged_as_app_error(app, client, caplog):
    import logging
    with caplog.at_level(logging.ERROR, logger='ams_errors'):
        rv = client.get('/favicon.ico')
    assert rv.status_code == 200
    assert rv.mimetype == 'image/png'
    assert rv.data[:8] == b'\x89PNG\r\n\x1a\n'
    assert 'Application Error' not in caplog.text


def test_routes_do_not_send_str_e_to_clients():
    leaks = _checker.find_leaks()
    assert leaks == [], 'Client-facing exception leaks:\n' + '\n'.join(leaks)
