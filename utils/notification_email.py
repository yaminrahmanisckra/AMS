"""
Send app notification emails (marks revealed, assessments, etc.) via
NOTIFICATION_MAIL_* only (noreply@kulawams.xyz).

Password recovery uses utils.recovery_email + MAIL_* (recovery@) — separate channel.
"""
from __future__ import annotations

import os

from flask import current_app


def _sync_notification_mail_from_os_environ():
    """
    Copy NOTIFICATION_MAIL_* from os.environ into app.config each send.
    Fixes cases where app.config was populated before cPanel/Passenger env was visible.
    """
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        return
    prefix = 'NOTIFICATION_MAIL_'
    for k, v in os.environ.items():
        if not k.startswith(prefix):
            continue
        if v is None:
            continue
        sv = str(v)
        if sv.strip() == '':
            continue
        if k.endswith('_PASSWORD'):
            app.config[k] = sv.rstrip('\r\n')
        else:
            app.config[k] = sv.strip()


def _notif_setting(key: str, default=None):
    """Prefer OS env (cPanel), then app.config."""
    v = os.environ.get(key)
    if v is not None and str(v).strip() != '':
        return v
    v = current_app.config.get(key)
    if v is not None and v != '':
        return v
    return default


def _user_intends_notification_mail_channel() -> bool:
    """True if env/config suggests noreply / NOTIFICATION channel should be used."""
    s = (_notif_setting('NOTIFICATION_MAIL_SENDER') or '').strip()
    u = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    return bool(s or u)


def _notification_smtp_configured() -> bool:
    _sync_notification_mail_from_os_environ()
    user = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    pwd = _notif_setting('NOTIFICATION_MAIL_PASSWORD')
    if isinstance(pwd, str):
        pwd = pwd.rstrip('\r\n')
    pwd_ok = pwd is not None and str(pwd).strip() != ''
    sender = (_notif_setting('NOTIFICATION_MAIL_SENDER') or _notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    return bool(user and pwd_ok and sender)


def _notif_bool(key: str, fallback=False) -> bool:
    raw = _notif_setting(key, fallback)
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _entry_subject(entry: dict, default_subject: str | None) -> str:
    return (entry.get('subject') or default_subject or '').strip() or 'AMS notification'


def send_notification_batch(subject: str | None, entries: list[dict]) -> int:
    """
    Send one email per entry (privacy). Each entry: recipient (str), text_body,
    html_body (optional), subject (optional; overrides batch subject).

    Uses NOTIFICATION_MAIL_* (noreply@) only — never recovery@ / MAIL_*.
    Returns number of messages accepted by SMTP.
    """
    if not entries:
        return 0

    _sync_notification_mail_from_os_environ()

    if not _notification_smtp_configured():
        current_app.logger.error(
            'notification email skipped: set NOTIFICATION_MAIL_USERNAME, '
            'NOTIFICATION_MAIL_PASSWORD, and NOTIFICATION_MAIL_SENDER '
            '(noreply@kulawams.xyz)'
        )
        return 0

    from utils.recovery_email import send_smtp_message

    user = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    sender = (
        (_notif_setting('NOTIFICATION_MAIL_SENDER') or '').strip() or user
    )
    password = _notif_setting('NOTIFICATION_MAIL_PASSWORD')
    host = _notif_setting('NOTIFICATION_MAIL_SERVER') or 'localhost'
    port = int(_notif_setting('NOTIFICATION_MAIL_PORT') or 25)
    use_tls = _notif_bool('NOTIFICATION_MAIL_USE_TLS', False)
    use_ssl = _notif_bool('NOTIFICATION_MAIL_USE_SSL', False)
    from_name = (
        _notif_setting('NOTIFICATION_MAIL_FROM_NAME') or ''
    ).strip() or None

    current_app.logger.info(
        'notification email path: NOTIFICATION_SMTP (noreply) sender=%s', sender
    )

    sent = 0
    for entry in entries:
        recipient = (entry.get('recipient') or '').strip()
        if not recipient:
            continue
        try:
            # Host rule: SMTP login and From must match
            send_smtp_message(
                host=host,
                port=port,
                use_tls=use_tls,
                use_ssl=use_ssl,
                user=user,
                password=password,
                sender=user,
                recipient=recipient,
                subject=_entry_subject(entry, subject),
                text_body=entry.get('text_body') or '',
                html_body=entry.get('html_body'),
                from_name=from_name,
                timeout=60,
                try_cpanel_alternatives=True,
            )
            sent += 1
        except Exception as one_err:
            current_app.logger.error(
                f'notification email failed to {recipient}: {one_err}',
                exc_info=True,
            )
    return sent
