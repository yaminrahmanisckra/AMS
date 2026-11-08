"""RupantorPay gateway client for Admission Exam online (MFS) payments."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = 'https://payment.rupantorpay.com'
REQUEST_TIMEOUT_SEC = 30


class RupantorPayError(Exception):
    """Raised when the gateway rejects a request or returns an unusable payload."""

    def __init__(self, message, *, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def api_key():
    return (os.environ.get('RUPANTORPAY_API_KEY') or '').strip()


def base_url():
    return (os.environ.get('RUPANTORPAY_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')


def is_configured():
    return bool(api_key())


def parse_fee_amount(raw):
    """Parse cycle.fee_amount into a float; return None if missing/invalid."""
    text = str(raw or '').strip().replace(',', '')
    if not text:
        return None
    # Allow "Tk. 500" / "500.00 BDT" — keep the first number token.
    match = re.search(r'(\d+(?:\.\d+)?)', text)
    if not match:
        return None
    try:
        amount = float(match.group(1))
    except ValueError:
        return None
    if amount <= 0:
        return None
    return amount


def format_amount(amount):
    """RupantorPay prefers whole numbers without trailing zeros when possible."""
    num = float(amount)
    if num == int(num):
        return str(int(num))
    return f'{num:.2f}'.rstrip('0').rstrip('.')


def amounts_match(expected, actual, *, tolerance=0.01):
    try:
        exp = float(expected)
        act = float(actual)
    except (TypeError, ValueError):
        return False
    return abs(exp - act) <= tolerance


def _post_json(path, body, *, client_host=None, include_client=True):
    key = api_key()
    if not key:
        raise RupantorPayError('RupantorPay is not configured (missing RUPANTORPAY_API_KEY).')

    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': key,
        'Accept': 'application/json',
    }
    if include_client:
        host = (client_host or '').strip()
        if host:
            headers['X-CLIENT'] = host

    url = f'{base_url()}{path}'
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            status_code = getattr(resp, 'status', 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        raise RupantorPayError(
            f'RupantorPay HTTP {exc.code}',
            status_code=exc.code,
            payload=_safe_json(raw) or raw,
        ) from exc
    except urllib.error.URLError as exc:
        raise RupantorPayError(f'RupantorPay network error: {exc.reason}') from exc

    payload = _safe_json(raw)
    if payload is None:
        raise RupantorPayError('RupantorPay returned non-JSON response.', status_code=status_code, payload=raw)
    return payload


def _safe_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def create_checkout(
    *,
    fullname,
    email,
    amount,
    success_url,
    cancel_url,
    webhook_url=None,
    metadata=None,
    client_host=None,
):
    """
    Create a payment link.

    Returns payment_url string. Raises RupantorPayError on failure.
    """
    body: dict[str, Any] = {
        'fullname': (fullname or '').strip() or 'Applicant',
        'email': (email or '').strip() or 'noreply@example.com',
        'amount': format_amount(amount),
        'success_url': success_url,
        'cancel_url': cancel_url,
    }
    if webhook_url:
        body['webhook_url'] = webhook_url
    # Docs alternate between meta_data and metadata — send both with same payload.
    meta = metadata if isinstance(metadata, dict) else {}
    body['metadata'] = meta
    body['meta_data'] = meta

    payload = _post_json('/api/payment/checkout', body, client_host=client_host)
    status = payload.get('status')
    payment_url = (payload.get('payment_url') or '').strip()
    ok = status in (1, True, '1', 'true', 'True') or bool(payment_url)
    if not ok or not payment_url:
        message = payload.get('message') or 'Could not create payment link.'
        raise RupantorPayError(str(message), payload=payload)
    if not payment_url.startswith('https://'):
        raise RupantorPayError('RupantorPay returned an invalid payment URL.', payload=payload)
    return payment_url


def verify_payment(transaction_id, *, client_host=None):
    """
    Verify a completed payment.

    Returns a normalized dict:
      status, transaction_id, trx_id, amount, payment_method, metadata, raw
    """
    txn = (transaction_id or '').strip()
    if not txn:
        raise RupantorPayError('Missing transaction_id.')

    payload = _post_json(
        '/api/payment/verify-payment',
        {'transaction_id': txn},
        client_host=client_host,
        include_client=False,
    )
    if payload.get('status') is False or payload.get('status') == 0:
        raise RupantorPayError(
            str(payload.get('message') or 'Payment verification failed.'),
            payload=payload,
        )

    status = str(payload.get('status') or '').strip().upper()
    metadata = payload.get('metadata') or payload.get('meta_data') or {}
    if isinstance(metadata, str):
        metadata = _safe_json(metadata) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    method = (
        payload.get('payment_method')
        or payload.get('paymentMethod')
        or ''
    )
    method = str(method).strip().lower()

    return {
        'status': status,
        'transaction_id': str(payload.get('transaction_id') or txn).strip(),
        'trx_id': str(payload.get('trx_id') or payload.get('transaction_id') or txn).strip(),
        'amount': payload.get('amount'),
        'payment_method': method or None,
        'fullname': payload.get('fullname') or payload.get('fullname'),
        'email': payload.get('email'),
        'currency': payload.get('currency'),
        'metadata': metadata,
        'raw': payload,
    }
