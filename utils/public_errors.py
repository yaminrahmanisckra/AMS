"""Redact unexpected exceptions in HTTP responses (LOG-01).

Use ``api_error`` / ``flash_exception`` in ``except Exception`` handlers.
Use ``client_message`` only when the exception was raised with a string that
is already safe to show (``ValueError``, ``AIClientError``, ``AIURLSafetyError``).
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Mapping

from flask import current_app, flash, has_app_context, jsonify

DEFAULT_PUBLIC_MESSAGE = (
    'Something went wrong. Please try again. '
    'If it continues, quote the reference id to the administrator.'
)


def new_error_id() -> str:
    return secrets.token_hex(6)


def report_exception(
    exc: BaseException,
    public_msg: str | None = None,
    **context: Any,
) -> tuple[str, str]:
    """Log the traceback and return ``(error_id, public_text)``."""
    error_id = new_error_id()
    logger = current_app.logger if has_app_context() else logging.getLogger('ams_errors')
    extra = ' '.join(f'{k}={v}' for k, v in context.items() if v is not None)
    try:
        logger.exception('error_id=%s %s', error_id, extra)
    except Exception:
        logging.getLogger('ams_errors').exception('error_id=%s %s', error_id, extra)
    msg = (public_msg or DEFAULT_PUBLIC_MESSAGE).strip() or DEFAULT_PUBLIC_MESSAGE
    return error_id, f'{msg} (ref: {error_id})'


def public_error_payload(
    exc: BaseException,
    public_msg: str | None = None,
    extra: Mapping[str, Any] | None = None,
    **context: Any,
) -> dict[str, Any]:
    error_id, text = report_exception(exc, public_msg, **context)
    payload: dict[str, Any] = {
        'success': False,
        'ok': False,
        'error': text,
        'message': text,
        'error_id': error_id,
    }
    if extra:
        payload.update(dict(extra))
    payload['error'] = text
    payload['message'] = text
    payload['error_id'] = error_id
    return payload


def api_error(
    exc: BaseException,
    public_msg: str | None = None,
    status: int = 500,
    extra: Mapping[str, Any] | None = None,
    **context: Any,
):
    """JSON error response: generic message + correlation id, never ``str(exc)``."""
    return jsonify(public_error_payload(exc, public_msg, extra, **context)), status


def flash_exception(
    exc: BaseException,
    public_msg: str | None = None,
    category: str = 'error',
    **context: Any,
) -> str:
    """Flash a generic message with a correlation id. Returns the public text."""
    _error_id, text = report_exception(exc, public_msg, **context)
    flash(text, category)
    return text


def client_message(exc: BaseException) -> str:
    """Pass through an exception that was raised with a user-facing message."""
    return str(exc)
