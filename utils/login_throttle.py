"""
Fail-open login throttling for the standard username/password login form.

Backed by the `login_throttle` table (see scripts/sql/phase3_security_schema.sql).
Keyed on a SHA-256 hash of username+IP so raw usernames/IPs are never persisted.

Every function here fails OPEN: if the table doesn't exist yet (migration not
run), the DB is unreachable, or any other error occurs, login proceeds as if
throttling were disabled rather than locking legitimate users out or crashing
the login page.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from sqlalchemy import text

from extensions import db

MAX_FAILED_ATTEMPTS = 8
LOCKOUT_WINDOW_MINUTES = 15


def _key_hash(username: str, ip: str) -> str:
    raw = f"{(username or '').strip().lower()}|{(ip or '').strip()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _user_key_hash(username: str) -> str:
    """Global per-username key so rotating IPs cannot bypass the lockout."""
    raw = f"user|{(username or '').strip().lower()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _as_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _is_key_locked(key_hash: str) -> bool:
    row = db.session.execute(
        text('SELECT locked_until FROM login_throttle WHERE key_hash = :key_hash'),
        {'key_hash': key_hash},
    ).fetchone()
    if not row:
        return False
    locked_until = _as_datetime(row[0])
    if not locked_until:
        return False
    return datetime.utcnow() < locked_until


def is_locked(username: str, ip: str) -> bool:
    """Return True only when an active lock is positively confirmed. Fails open (False)."""
    try:
        return _is_key_locked(_key_hash(username, ip)) or _is_key_locked(_user_key_hash(username))
    except Exception:
        logger.warning('login_throttle is_locked failed (fail-open)', exc_info=True)
        return False


def _bump_failure(key_hash: str, now: datetime) -> None:
    row = db.session.execute(
        text('SELECT fail_count, first_fail_at FROM login_throttle WHERE key_hash = :key_hash'),
        {'key_hash': key_hash},
    ).fetchone()

    if row is None:
        db.session.execute(
            text(
                'INSERT INTO login_throttle '
                '(key_hash, fail_count, first_fail_at, locked_until, updated_at) '
                'VALUES (:key_hash, 1, :now, NULL, :now)'
            ),
            {'key_hash': key_hash, 'now': now},
        )
        return

    fail_count = row[0] or 0
    first_fail_at = _as_datetime(row[1])
    window_expired = (
        first_fail_at is None
        or (now - first_fail_at) > timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    )
    if window_expired:
        fail_count = 1
        first_fail_at = now
    else:
        fail_count += 1

    locked_until = now + timedelta(minutes=LOCKOUT_WINDOW_MINUTES) if fail_count >= MAX_FAILED_ATTEMPTS else None
    db.session.execute(
        text(
            'UPDATE login_throttle SET fail_count = :fail_count, first_fail_at = :first_fail_at, '
            'locked_until = :locked_until, updated_at = :now WHERE key_hash = :key_hash'
        ),
        {
            'fail_count': fail_count,
            'first_fail_at': first_fail_at,
            'locked_until': locked_until,
            'now': now,
            'key_hash': key_hash,
        },
    )


def record_failure(username: str, ip: str) -> None:
    """Record one failed login attempt; lock after MAX_FAILED_ATTEMPTS within LOCKOUT_WINDOW_MINUTES.

    Counts both username+IP and username-only so IP rotation cannot reset the lock.
    Fails open (no-op) on any error so a missing/broken table never blocks login.
    """
    try:
        now = datetime.utcnow()
        _bump_failure(_key_hash(username, ip), now)
        _bump_failure(_user_key_hash(username), now)
        db.session.commit()
    except Exception:
        logger.warning('login_throttle record_failure failed (fail-open)', exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass


def clear(username: str, ip: str) -> None:
    """Clear throttle state after a successful login. Fails open (no-op) on any error."""
    try:
        db.session.execute(
            text(
                'DELETE FROM login_throttle WHERE key_hash = :ip_key OR key_hash = :user_key'
            ),
            {
                'ip_key': _key_hash(username, ip),
                'user_key': _user_key_hash(username),
            },
        )
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
