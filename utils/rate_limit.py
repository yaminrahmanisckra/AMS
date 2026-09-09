"""Shared DB-backed rate limits (Passenger-safe; not in-memory).

Keys are SHA-256 hashes so raw IPs/emails are not stored. Missing-table or
DB errors fail open unless RATE_LIMIT_FAIL_CLOSED is set, and always log.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from types import SimpleNamespace

from flask import jsonify, make_response
from sqlalchemy.exc import IntegrityError

from extensions import db

logger = logging.getLogger(__name__)

# (max_requests, window_seconds) — audit Phase 1.1
LOGIN_IP = (30, 60)
LOGIN_USERNAME = (10, 15 * 60)
FORGOT_IP = (5, 3600)
FORGOT_EMAIL = (3, 3600)
VERIFY_IP = (20, 15 * 60)
RESET_IP = (10, 3600)
ADMISSION_LOGIN_IP = (20, 3600)
ADMISSION_LOGIN_APP = (5, 15 * 60)
FEEDBACK_IP = (20, 3600)
AI_USER = (20, 3600)
AI_BATCH = (5, 3600)
PDF_EXPORT = (30, 3600)


class RateLimitBucket(db.Model):
    __tablename__ = 'rate_limit_bucket'

    bucket_key = db.Column(db.String(64), primary_key=True)
    window_start = db.Column(db.DateTime, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)


def _fail_closed() -> bool:
    return (os.getenv('RATE_LIMIT_FAIL_CLOSED') or '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


def _bucket_key(scope: str, identity: str) -> str:
    raw = f"{scope}|{(identity or '').strip().lower()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def consume(scope: str, identity: str, limit: int, window_seconds: int):
    """Increment the bucket. Returns {allowed, retry_after}."""
    denied = SimpleNamespace(allowed=False, retry_after=max(1, int(window_seconds)))
    allowed = SimpleNamespace(allowed=True, retry_after=0)
    limit = int(limit)
    window_seconds = int(window_seconds)
    try:
        key = _bucket_key(scope, identity)
        now = datetime.utcnow()
        row = RateLimitBucket.query.filter_by(bucket_key=key).first()
        if row is None:
            db.session.add(RateLimitBucket(bucket_key=key, window_start=now, count=1))
            try:
                db.session.commit()
                return allowed if 1 <= limit else denied
            except IntegrityError:
                db.session.rollback()
                row = RateLimitBucket.query.filter_by(bucket_key=key).first()
                if row is None:
                    return denied if _fail_closed() else allowed

        elapsed = (now - row.window_start).total_seconds()
        if elapsed >= window_seconds:
            row.window_start = now
            row.count = 1
            elapsed = 0
        else:
            row.count = (row.count or 0) + 1
        db.session.commit()
        if row.count > limit:
            return SimpleNamespace(allowed=False, retry_after=max(1, int(window_seconds - elapsed)))
        return allowed
    except Exception:
        logger.warning(
            'rate_limit consume failed (fail-%s)',
            'closed' if _fail_closed() else 'open',
            exc_info=True,
        )
        try:
            db.session.rollback()
        except Exception:
            pass
        return denied if _fail_closed() else allowed


def first_blocked(*specs):
    """Consume every (scope, identity, limit, window) spec; return the first denial."""
    blocked = None
    for spec in specs:
        scope, identity, limit, window = spec
        result = consume(scope, identity, int(limit), int(window))
        if not result.allowed and blocked is None:
            blocked = result
    return blocked


def reject_if_user_limited(scope, limit_pair, json_message=None, html=None):
    """Limit the logged-in user, else the client IP."""
    from flask_login import current_user
    from utils.request_ip import client_ip

    if current_user and getattr(current_user, 'is_authenticated', False):
        ident = f'user:{current_user.id}'
    else:
        ident = f'ip:{client_ip()}'
    blocked = first_blocked((scope, ident, *limit_pair))
    if not blocked:
        return None
    json_body = None
    if json_message is not None:
        json_body = {'success': False, 'message': json_message}
    return reject_too_many(blocked, html=html, json_body=json_body)


def reject_too_many(blocked, html=None, json_body=None):
    retry = max(1, int(getattr(blocked, 'retry_after', 1) or 1))
    if json_body is not None:
        resp = jsonify(json_body)
        resp.status_code = 429
    elif html is not None:
        resp = make_response(html, 429)
    else:
        resp = make_response('Too many requests. Please try again later.', 429)
    resp.headers['Retry-After'] = str(retry)
    return resp
