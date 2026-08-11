"""Bangladesh timezone helpers for display (Asia/Dhaka, UTC+6).

Storage convention in this app is naive UTC via ``datetime.utcnow()``.
Convert only when formatting for humans. Do not convert:
- wall-clock fields already entered as BD local (e.g. admission apply windows)
- pure ``time`` / calendar schedule times
- UTC protocol stamps (ICS ``Z``, filenames)
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Union

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

BD_TZ_NAME = 'Asia/Dhaka'
_BD_OFFSET = timedelta(hours=6)

DateLike = Union[datetime, date, time, None]


def _bd_zone():
    if ZoneInfo is not None:
        try:
            return ZoneInfo(BD_TZ_NAME)
        except Exception:
            pass
    return timezone(_BD_OFFSET)


def bd_now() -> datetime:
    """Aware current time in Asia/Dhaka."""
    return datetime.now(_bd_zone())


def bd_now_naive() -> datetime:
    """Current Bangladesh wall time as naive datetime (for comparing BD wall fields)."""
    return bd_now().replace(tzinfo=None)


def to_bd(value: DateLike, *, assume_utc: bool = True) -> DateLike:
    """Convert a stored UTC datetime to Bangladesh local time.

    - ``None`` → ``None``
    - ``date`` / ``time`` → returned unchanged (not UTC timestamps)
    - aware datetime → converted to Asia/Dhaka
    - naive datetime → treated as UTC when ``assume_utc`` (app default)
    """
    if value is None:
        return None
    if isinstance(value, time) and not isinstance(value, datetime):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, datetime):
        return value

    zone = _bd_zone()
    if value.tzinfo is not None:
        return value.astimezone(zone)
    if assume_utc:
        return value.replace(tzinfo=timezone.utc).astimezone(zone)
    return value.replace(tzinfo=zone)


def _coerce_datetime(value) -> DateLike:
    """Accept datetime/date/time or common ISO/SQLite datetime strings."""
    if value is None or isinstance(value, (datetime, date, time)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        s2 = s.replace('Z', '+00:00')
        if ' ' in s2 and 'T' not in s2:
            s2 = s2.replace(' ', 'T', 1)
        try:
            return datetime.fromisoformat(s2)
        except Exception:
            for pattern in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    return datetime.strptime(s[:26], pattern)
                except Exception:
                    continue
    return None


def format_bd(
    value,
    fmt: str = '%Y-%m-%d %H:%M',
    *,
    assume_utc: bool = True,
    default: str = '',
) -> str:
    """Format a value in Bangladesh time. Returns ``default`` if value is None."""
    value = _coerce_datetime(value)
    if value is None:
        return default
    converted = to_bd(value, assume_utc=assume_utc)
    if converted is None:
        return default
    if isinstance(converted, datetime):
        return converted.strftime(fmt)
    if isinstance(converted, (date, time)):
        return converted.strftime(fmt)
    return default


def register_template_filters(app) -> None:
    """Register Jinja filters: ``bd``, ``bd_date``, ``bd_time``."""

    @app.template_filter('bd')
    def bd_filter(value, fmt='%Y-%m-%d %H:%M', assume_utc=True):
        """UTC datetime → Bangladesh wall time string.

        Usage: ``{{ created_at|bd('%d %b %Y, %I:%M %p') }}``
        For fields already stored as BD wall time:
        ``{{ apply_end|bd('%d %B %Y, %I:%M %p', assume_utc=False) }}``
        """
        return format_bd(value, fmt, assume_utc=bool(assume_utc), default='')

    @app.template_filter('bd_date')
    def bd_date_filter(value, fmt='%Y-%m-%d'):
        return format_bd(value, fmt, assume_utc=True, default='')

    @app.template_filter('bd_time')
    def bd_time_filter(value, fmt='%I:%M %p'):
        return format_bd(value, fmt, assume_utc=True, default='')
